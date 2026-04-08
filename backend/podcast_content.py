import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Optional
import socket
import ipaddress
from urllib.parse import urlparse, urljoin

import firebase_admin
import httpx
import requests
from firebase_admin import storage


APP_ENV = os.getenv("APP_ENV", "production")
PUBLIC_APP_URL = (os.getenv("PUBLIC_APP_URL") or "").rstrip("/")
MAX_PODCAST_TEXT_CHARS = int(os.getenv("MAX_PODCAST_TEXT_CHARS", "12000"))
MAX_PODCAST_INTRO_CHARS = int(os.getenv("MAX_PODCAST_INTRO_CHARS", "1200"))
PODCAST_TARGET_LOUDNESS_LUFS = os.getenv("PODCAST_TARGET_LOUDNESS_LUFS", "-16")
PODCAST_TARGET_TRUE_PEAK_DBTP = os.getenv("PODCAST_TARGET_TRUE_PEAK_DBTP", "-1.5")
PODCAST_TARGET_LOUDNESS_RANGE = os.getenv("PODCAST_TARGET_LOUDNESS_RANGE", "11")
PODCAST_FETCH_TIMEOUT_SECONDS = float(os.getenv("PODCAST_FETCH_TIMEOUT_SECONDS", "15"))
PODCAST_FETCH_USER_AGENT = os.getenv(
    "PODCAST_FETCH_USER_AGENT",
    "AnalyzeThisPodcastBot/1.0 (+https://analyzethis.app)",
)


@dataclass
class EpisodeContent:
    intro_text: Optional[str]
    body_text: Optional[str]
    body_source: str


def build_shared_item_url(item_id: str) -> Optional[str]:
    if PUBLIC_APP_URL:
        return f"{PUBLIC_APP_URL}/?item={item_id}"
    if APP_ENV == "development":
        return f"/?item={item_id}"
    return None


def _read_local_blob(blob_path: str) -> bytes:
    local_path = Path("static") / blob_path
    return local_path.read_bytes()


def read_blob_bytes(blob_path: str) -> bytes:
    if APP_ENV == "development":
        return _read_local_blob(blob_path)

    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET')})

    bucket = storage.bucket()
    blob = bucket.blob(blob_path)
    return blob.download_as_bytes()


def upload_audio_bytes(blob_path: str, audio_bytes: bytes, mime_type: str) -> str:
    if APP_ENV == "development":
        local_path = Path("static") / blob_path
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(audio_bytes)
        return blob_path

    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET')})

    bucket = storage.bucket()
    blob = bucket.blob(blob_path)
    blob.upload_from_string(audio_bytes, content_type=mime_type)
    return blob_path


def concatenate_mp3_segments(segments: list[bytes]) -> bytes:
    if not segments:
        raise RuntimeError("missing_audio_segments")
    if len(segments) == 1:
        return segments[0]

    with tempfile.TemporaryDirectory(prefix="podcast-concat-") as temp_dir:
        temp_path = Path(temp_dir)
        segment_paths = []
        for index, segment in enumerate(segments):
            segment_path = temp_path / f"segment-{index:04d}.mp3"
            segment_path.write_bytes(segment)
            segment_paths.append(segment_path)

        concat_file = temp_path / "concat.txt"
        concat_file.write_text(
            "".join(f"file '{path.name}'\n" for path in segment_paths),
            encoding="utf-8",
        )

        output_path = temp_path / "joined.mp3"
        _run_ffmpeg(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                str(output_path),
            ],
            cwd=temp_path,
        )
        return output_path.read_bytes()


def normalize_audio_bytes(audio_bytes: bytes, mime_type: str) -> tuple[bytes, str]:
    if not audio_bytes:
        raise RuntimeError("missing_audio_bytes")

    input_extension = ".wav" if mime_type == "audio/wav" else ".mp3"
    output_extension = ".wav" if mime_type == "audio/wav" else ".mp3"
    output_mime_type = "audio/wav" if mime_type == "audio/wav" else "audio/mpeg"

    with tempfile.TemporaryDirectory(prefix="podcast-normalize-") as temp_dir:
        temp_path = Path(temp_dir)
        input_path = temp_path / f"input{input_extension}"
        output_path = temp_path / f"normalized{output_extension}"
        input_path.write_bytes(audio_bytes)

        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(input_path),
            "-af",
            (
                "loudnorm="
                f"I={PODCAST_TARGET_LOUDNESS_LUFS}:"
                f"TP={PODCAST_TARGET_TRUE_PEAK_DBTP}:"
                f"LRA={PODCAST_TARGET_LOUDNESS_RANGE}"
            ),
        ]
        if output_mime_type == "audio/mpeg":
            command.extend(["-codec:a", "libmp3lame", "-b:a", "192k"])
        command.append(str(output_path))

        _run_ffmpeg(command)
        return output_path.read_bytes(), output_mime_type


def extract_podcast_text(item: dict) -> Optional[str]:
    item_type = (item.get("type") or "").lower()
    if item_type == "text":
        return _truncate_text(item.get("content"))

    if item_type == "web_url":
        return _extract_remote_text(item.get("content"))

    if item_type == "audio":
        return None

    if item_type != "file":
        return None

    blob_path = item.get("content")
    if not blob_path:
        return None

    mime_type = ((item.get("item_metadata") or {}).get("mimeType") or "").lower()
    filename = ((item.get("item_metadata") or {}).get("fileName") or blob_path).lower()
    raw_bytes = read_blob_bytes(blob_path)

    if mime_type == "application/pdf" or filename.endswith(".pdf"):
        return _truncate_text(_extract_pdf_text(raw_bytes))

    if mime_type.startswith("text/") or filename.endswith(".txt"):
        return _truncate_text(raw_bytes.decode("utf-8", errors="ignore"))

    return None


def resolve_episode_content(item: dict, analysis: dict) -> EpisodeContent:
    intro_text = _truncate_intro_text(
        analysis.get("podcast_summary") or analysis.get("overview") or ""
    )
    body_text = extract_podcast_text(item)
    body_source = "item_content" if body_text else "none"

    if not body_text:
        source_url = ((item.get("item_metadata") or {}).get("sourceUrl") or "").strip()
        if source_url:
            body_text = _extract_remote_text(source_url)
            if body_text:
                body_source = "source_url"

    return EpisodeContent(
        intro_text=intro_text,
        body_text=body_text,
        body_source=body_source,
    )


def build_podcast_script(item: dict, analysis: dict, episode: EpisodeContent | None = None) -> str:
    title = analysis.get("podcast_title") or item.get("title") or "Untitled item"
    episode = episode or resolve_episode_content(item, analysis)

    parts = [title]

    if episode.intro_text:
        parts.append(
            _clean_podcast_script_text(
                f"First, a quick analysis.\n\n{episode.intro_text}"
            )
        )

    if episode.body_text:
        if episode.intro_text:
            parts.append("Now let's get into the original piece.")
        parts.append(episode.body_text)
    elif episode.intro_text:
        parts.append("The original source content could not be retrieved, so this episode includes the analysis summary only.")
    else:
        parts.append("This shared item is now available in your podcast feed.")

    return _clean_podcast_script_text("\n\n".join(parts).strip())


def get_episode_body_source(item: dict, analysis: dict) -> str:
    return resolve_episode_content(item, analysis).body_source


def build_podcast_notes(item: dict, analysis: dict) -> Optional[str]:
    parts = []
    overview = analysis.get("overview")
    if overview:
        parts.append(str(overview).strip())

    tags = analysis.get("tags") or []
    if tags:
        parts.append("Tags: " + ", ".join(str(tag) for tag in tags[:10]))

    link = build_shared_item_url(item.get("firestore_id") or item.get("id") or "")
    if link:
        parts.append(f"Shared item: {link}")

    if not parts:
        return None
    return "\n\n".join(parts)


def _truncate_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return text
    cleaned = _clean_podcast_script_text(str(text))
    if len(cleaned) <= MAX_PODCAST_TEXT_CHARS:
        return cleaned
    truncated = cleaned[:MAX_PODCAST_TEXT_CHARS]
    return truncated.rsplit(" ", 1)[0]


def _truncate_intro_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return text
    cleaned = _clean_podcast_script_text(str(text))
    if len(cleaned) <= MAX_PODCAST_INTRO_CHARS:
        return cleaned
    truncated = cleaned[:MAX_PODCAST_INTRO_CHARS]
    return truncated.rsplit(" ", 1)[0]


def _extract_pdf_text(raw_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
    except Exception:
        return ""

    try:
        from io import BytesIO

        reader = PdfReader(BytesIO(raw_bytes))
        extracted = []
        for page in reader.pages:
            extracted.append(page.extract_text() or "")
        return "\n".join(extracted)
    except Exception:
        return ""


def _resolve_and_validate_ip(hostname: str) -> Optional[str]:
    """Resolves hostname and validates it is a safe, public IP address to prevent SSRF."""
    try:
        # Resolve hostname to IP
        ip_str = socket.gethostbyname(hostname)
        ip_obj = ipaddress.ip_address(ip_str)

        # Explicitly check for 0.0.0.0 (unspecified) and link-local, private, loopback
        if str(ip_obj) == "0.0.0.0" or ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_unspecified:
            return None

        return ip_str
    except Exception:
        return None

def _extract_remote_text(source_url: str) -> Optional[str]:
    if not source_url:
        return None

    try:
        # Use httpx with manual redirect following to validate each step
        with httpx.Client(
            timeout=PODCAST_FETCH_TIMEOUT_SECONDS,
            headers={"User-Agent": PODCAST_FETCH_USER_AGENT},
            follow_redirects=False
        ) as client:
            current_url = source_url
            response = None
            max_redirects = 5

            for _ in range(max_redirects):
                parsed_url = urlparse(current_url)
                hostname = parsed_url.hostname
                if not hostname:
                    return None

                ip_str = _resolve_and_validate_ip(hostname)
                if not ip_str:
                    return None

                # Protect against DNS rebinding by connecting directly to the validated IP,
                # but pass the original Host header.
                safe_url = f"{parsed_url.scheme}://{ip_str}"
                if parsed_url.port:
                    safe_url += f":{parsed_url.port}"
                safe_url += f"{parsed_url.path}"
                if parsed_url.query:
                    safe_url += f"?{parsed_url.query}"
                if parsed_url.fragment:
                    safe_url += f"#{parsed_url.fragment}"

                headers = {"User-Agent": PODCAST_FETCH_USER_AGENT, "Host": hostname}

                response = client.get(safe_url, headers=headers)

                if response.is_redirect:
                    next_url = response.headers.get("Location")
                    if not next_url:
                        return None
                    # Handle relative redirects securely
                    current_url = urljoin(current_url, next_url)
                    continue

                response.raise_for_status()
                break
            else:
                # Too many redirects
                return None

    except Exception:
        return None

    content_type = (response.headers.get("content-type") or "").lower()
    if "application/pdf" in content_type or source_url.lower().endswith(".pdf"):
        return _truncate_text(_extract_pdf_text(response.content))

    text = _extract_html_text(response.text if response.text else response.content.decode("utf-8", errors="ignore"))
    return _truncate_text(text)


def _extract_html_text(html: str) -> str:
    if not html:
        return ""

    cleaned = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", html)
    cleaned = re.sub(r"(?i)</(p|div|article|section|h1|h2|h3|h4|h5|h6|li|blockquote|br)>", "\n\n", cleaned)
    cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
    cleaned = unescape(cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n\s*\n\s*\n+", "\n\n", cleaned)
    return _clean_podcast_script_text(cleaned)


def _clean_podcast_script_text(text: str) -> str:
    paragraphs = []
    for block in str(text).replace("\r\n", "\n").split("\n\n"):
        cleaned_block = " ".join(line.strip() for line in block.splitlines() if line.strip())
        if cleaned_block:
            paragraphs.append(cleaned_block)
    return "\n\n".join(paragraphs)


def _run_ffmpeg(command: list[str], cwd: Path | None = None) -> None:
    try:
        subprocess.run(command, cwd=cwd, check=True, capture_output=True)
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg_not_installed") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="ignore").strip()
        raise RuntimeError(f"ffmpeg_failed:{stderr or exc.returncode}") from exc
