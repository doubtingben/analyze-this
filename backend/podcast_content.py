import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import firebase_admin
from firebase_admin import storage


APP_ENV = os.getenv("APP_ENV", "production")
PUBLIC_APP_URL = (os.getenv("PUBLIC_APP_URL") or "").rstrip("/")
MAX_PODCAST_TEXT_CHARS = int(os.getenv("MAX_PODCAST_TEXT_CHARS", "12000"))
PODCAST_TARGET_LOUDNESS_LUFS = os.getenv("PODCAST_TARGET_LOUDNESS_LUFS", "-16")
PODCAST_TARGET_TRUE_PEAK_DBTP = os.getenv("PODCAST_TARGET_TRUE_PEAK_DBTP", "-1.5")
PODCAST_TARGET_LOUDNESS_RANGE = os.getenv("PODCAST_TARGET_LOUDNESS_RANGE", "11")


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


def build_podcast_script(item: dict, analysis: dict) -> str:
    text = extract_podcast_text(item)
    title = analysis.get("podcast_title") or item.get("title") or "Untitled item"
    summary = analysis.get("podcast_summary") or analysis.get("overview") or ""

    if text:
        body = text
    else:
        body = summary or "This shared item is now available in your podcast feed."

    return _clean_podcast_script_text(f"{title}\n\n{body}".strip())


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
