import os
import re
import json
import subprocess
import tempfile
import logging
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Optional

import firebase_admin
import requests
from firebase_admin import storage
from openai import OpenAI


APP_ENV = os.getenv("APP_ENV", "production")
PUBLIC_APP_URL = (os.getenv("PUBLIC_APP_URL") or "").rstrip("/")
MAX_PODCAST_TEXT_CHARS = int(os.getenv("MAX_PODCAST_TEXT_CHARS", "12000"))
MAX_PODCAST_INTRO_CHARS = int(os.getenv("MAX_PODCAST_INTRO_CHARS", "1200"))
PODCAST_CONTENT_RETRIEVER = os.getenv("PODCAST_CONTENT_RETRIEVER", "deterministic").lower()
PODCAST_RETRIEVER_MODEL = os.getenv(
    "PODCAST_RETRIEVER_MODEL",
    os.getenv("OPENAI_MODEL", os.getenv("OPENROUTER_MODEL", "gemma4:31b")),
)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", os.getenv("OPENROUTER_API_KEY", "ollama"))
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", os.getenv("OPENROUTER_BASE_URL", "http://nixos-gpt:11434/v1"))
PODCAST_TARGET_LOUDNESS_LUFS = os.getenv("PODCAST_TARGET_LOUDNESS_LUFS", "-16")
PODCAST_TARGET_TRUE_PEAK_DBTP = os.getenv("PODCAST_TARGET_TRUE_PEAK_DBTP", "-1.5")
PODCAST_TARGET_LOUDNESS_RANGE = os.getenv("PODCAST_TARGET_LOUDNESS_RANGE", "11")
PODCAST_FETCH_TIMEOUT_SECONDS = float(os.getenv("PODCAST_FETCH_TIMEOUT_SECONDS", "15"))
PODCAST_FETCH_USER_AGENT = os.getenv(
    "PODCAST_FETCH_USER_AGENT",
    "AnalyzeThisPodcastBot/1.0 (+https://analyzethis.app)",
)
logger = logging.getLogger(__name__)

client = None
if OPENAI_API_KEY:
    try:
        client = OpenAI(base_url=OPENAI_BASE_URL, api_key=OPENAI_API_KEY)
    except Exception as exc:
        logger.error("Failed to initialize podcast retriever client: %s", exc)


@dataclass
class EpisodeContent:
    intro_text: Optional[str]
    body_text: Optional[str]
    body_source: str
    retrieval_error: Optional[str] = None
    retrieval_details: dict | None = None


@dataclass
class PodcastRetrievalRequest:
    item_id: str
    user_email: str
    item_type: str
    title: Optional[str]
    content: Optional[str]
    item_metadata: dict
    analysis: dict
    max_chars: int = MAX_PODCAST_TEXT_CHARS


@dataclass
class PodcastRetrievalResult:
    body_text: Optional[str]
    body_source: str
    retrieval_error: Optional[str] = None
    retrieval_details: dict | None = None


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


def probe_audio_duration_seconds(audio_bytes: bytes, mime_type: str) -> Optional[int]:
    if not audio_bytes:
        return None

    input_extension = ".wav" if mime_type == "audio/wav" else ".mp3"
    with tempfile.TemporaryDirectory(prefix="podcast-probe-") as temp_dir:
        input_path = Path(temp_dir) / f"input{input_extension}"
        input_path.write_bytes(audio_bytes)

        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(input_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            logger.warning("ffprobe is not installed; podcast duration_seconds will be omitted")
            return None
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            logger.warning("ffprobe failed while reading podcast duration: %s", stderr or exc.returncode)
            return None

    duration_text = result.stdout.strip()
    if not duration_text or duration_text == "N/A":
        return None

    try:
        return max(1, round(float(duration_text)))
    except ValueError:
        logger.warning("ffprobe returned invalid podcast duration: %s", duration_text)
        return None


def extract_podcast_text(item: dict) -> Optional[str]:
    text, _details = extract_podcast_text_with_diagnostics(item)
    return text


def resolve_episode_content(item: dict, analysis: dict) -> EpisodeContent:
    intro_text = _truncate_intro_text(
        analysis.get("podcast_summary") or analysis.get("overview") or ""
    )
    request = PodcastRetrievalRequest(
        item_id=item.get("firestore_id") or item.get("id") or "",
        user_email=item.get("user_email") or "",
        item_type=(item.get("type") or "").lower(),
        title=item.get("title"),
        content=item.get("content"),
        item_metadata=item.get("item_metadata") or {},
        analysis=analysis or {},
    )
    result = retrieve_podcast_content(request)

    return EpisodeContent(
        intro_text=intro_text,
        body_text=result.body_text,
        body_source=result.body_source,
        retrieval_error=result.retrieval_error,
        retrieval_details=result.retrieval_details,
    )


def retrieve_podcast_content(request: PodcastRetrievalRequest) -> PodcastRetrievalResult:
    deterministic_result = _retrieve_podcast_content_deterministic(request)
    if PODCAST_CONTENT_RETRIEVER != "agentic":
        return deterministic_result

    try:
        agentic_result = _retrieve_podcast_content_agentic(request, deterministic_result)
        if agentic_result.body_text:
            return agentic_result
        return _merge_retrieval_fallback(deterministic_result, agentic_result)
    except Exception as exc:
        logger.warning("Agentic podcast content retrieval failed; using deterministic result: %s", exc)
        fallback_details = deterministic_result.retrieval_details or {}
        return PodcastRetrievalResult(
            body_text=deterministic_result.body_text,
            body_source=deterministic_result.body_source,
            retrieval_error=deterministic_result.retrieval_error,
            retrieval_details={
                **fallback_details,
                "strategy": "deterministic_fallback",
                "agentic_error": f"{type(exc).__name__}:{exc}",
            },
        )


def _retrieve_podcast_content_deterministic(request: PodcastRetrievalRequest) -> PodcastRetrievalResult:
    item = {
        "firestore_id": request.item_id,
        "user_email": request.user_email,
        "type": request.item_type,
        "title": request.title,
        "content": request.content,
        "item_metadata": request.item_metadata,
    }
    body_text, retrieval_details = extract_podcast_text_with_diagnostics(item)
    body_source = "item_content" if body_text else "none"
    retrieval_error = retrieval_details.get("failure_reason")

    if not body_text:
        source_url = (request.item_metadata.get("sourceUrl") or "").strip()
        if source_url:
            body_text, remote_details = _extract_remote_text_with_diagnostics(source_url)
            if body_text:
                body_source = "source_url"
                retrieval_details = remote_details
                retrieval_error = None
            else:
                retrieval_details = remote_details
                retrieval_error = remote_details.get("failure_reason")

    return PodcastRetrievalResult(
        body_text=_truncate_text_to_limit(body_text, request.max_chars),
        body_source=body_source,
        retrieval_error=retrieval_error,
        retrieval_details={
            **(retrieval_details or {}),
            "strategy": "deterministic",
        },
    )


def _retrieve_podcast_content_agentic(
    request: PodcastRetrievalRequest,
    deterministic_result: PodcastRetrievalResult,
) -> PodcastRetrievalResult:
    if not client:
        raise RuntimeError("podcast_retriever_client_not_initialized")

    candidates = _build_agentic_retrieval_candidates(request)
    if deterministic_result.body_text and not any(candidate.get("body_text") for candidate in candidates):
        candidates.append({
            "source": deterministic_result.body_source,
            "body_text": deterministic_result.body_text,
            "details": deterministic_result.retrieval_details or {},
        })

    prompt = (
        "You retrieve source content for private podcast narration. "
        "Use only the provided item fields and Python-collected candidate text. "
        "Do not invent source text. Do not summarize. Select and clean the best readable source text, "
        "preserving the original meaning and paragraph structure. Respect max_chars. "
        "Return only JSON with keys: body_text, body_source, retrieval_error, retrieval_details."
    )
    payload = {
        "item": {
            "item_id": request.item_id,
            "item_type": request.item_type,
            "title": request.title,
            "content": _safe_preview(request.content, 1000),
            "item_metadata": request.item_metadata,
            "analysis": {
                "overview": request.analysis.get("overview"),
                "podcast_title": request.analysis.get("podcast_title"),
                "podcast_summary": request.analysis.get("podcast_summary"),
            },
        },
        "max_chars": request.max_chars,
        "candidates": candidates,
        "deterministic_result": {
            "body_source": deterministic_result.body_source,
            "retrieval_error": deterministic_result.retrieval_error,
            "retrieval_details": deterministic_result.retrieval_details,
        },
    }

    completion = client.chat.completions.create(
        model=PODCAST_RETRIEVER_MODEL,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload, default=str)},
        ],
        response_format={"type": "json_object"},
    )
    result_content = completion.choices[0].message.content or "{}"
    parsed = json.loads(result_content)
    result = _parse_agentic_retrieval_result(parsed, request.max_chars)
    details = result.retrieval_details or {}
    return PodcastRetrievalResult(
        body_text=result.body_text,
        body_source=result.body_source,
        retrieval_error=result.retrieval_error,
        retrieval_details={
            **details,
            "strategy": "agentic",
            "candidate_count": len(candidates),
        },
    )


def _build_agentic_retrieval_candidates(request: PodcastRetrievalRequest) -> list[dict]:
    candidates = []
    item = {
        "firestore_id": request.item_id,
        "user_email": request.user_email,
        "type": request.item_type,
        "title": request.title,
        "content": request.content,
        "item_metadata": request.item_metadata,
    }

    body_text, details = extract_podcast_text_with_diagnostics(item)
    candidates.append({
        "source": "item_content",
        "body_text": _truncate_text_to_limit(body_text, request.max_chars),
        "details": details,
    })

    source_url = (request.item_metadata.get("sourceUrl") or "").strip()
    if source_url and source_url != request.content:
        remote_text, remote_details = _extract_remote_text_with_diagnostics(source_url)
        candidates.append({
            "source": "source_url",
            "body_text": _truncate_text_to_limit(remote_text, request.max_chars),
            "details": remote_details,
        })

    return candidates


def _parse_agentic_retrieval_result(parsed: dict, max_chars: int) -> PodcastRetrievalResult:
    if not isinstance(parsed, dict):
        return PodcastRetrievalResult(
            body_text=None,
            body_source="none",
            retrieval_error="agent_invalid_json_shape",
            retrieval_details={"raw_type": type(parsed).__name__},
        )

    body_text = _truncate_text_to_limit(parsed.get("body_text"), max_chars)
    body_source = parsed.get("body_source") or ("agentic" if body_text else "none")
    retrieval_error = parsed.get("retrieval_error")
    if not body_text and not retrieval_error:
        retrieval_error = "agent_no_text_returned"
    details = parsed.get("retrieval_details")
    if not isinstance(details, dict):
        details = {"agent_retrieval_details_type": type(details).__name__}

    return PodcastRetrievalResult(
        body_text=body_text,
        body_source=str(body_source),
        retrieval_error=str(retrieval_error) if retrieval_error else None,
        retrieval_details=details,
    )


def _merge_retrieval_fallback(
    deterministic_result: PodcastRetrievalResult,
    agentic_result: PodcastRetrievalResult,
) -> PodcastRetrievalResult:
    details = deterministic_result.retrieval_details or {}
    return PodcastRetrievalResult(
        body_text=deterministic_result.body_text,
        body_source=deterministic_result.body_source,
        retrieval_error=deterministic_result.retrieval_error,
        retrieval_details={
            **details,
            "strategy": "deterministic_fallback",
            "agentic_error": agentic_result.retrieval_error,
            "agentic_details": agentic_result.retrieval_details,
        },
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


def extract_podcast_text_with_diagnostics(item: dict) -> tuple[Optional[str], dict]:
    item_type = (item.get("type") or "").lower()
    item_metadata = item.get("item_metadata") or {}

    if item_type == "text":
        text = _truncate_text(item.get("content"))
        return text, {
            "source": "item_content",
            "item_type": item_type,
            "text_length": len(text or ""),
            "failure_reason": None if text else "empty_text_content",
        }

    if item_type == "web_url":
        source_url = item.get("content")
        text, details = _extract_remote_text_with_diagnostics(source_url)
        details.setdefault("source", "item_content")
        details.setdefault("item_type", item_type)
        return text, details

    if item_type == "audio":
        return None, {
            "source": "item_content",
            "item_type": item_type,
            "failure_reason": "audio_source_has_no_text",
        }

    if item_type != "file":
        return None, {
            "source": "item_content",
            "item_type": item_type or "unknown",
            "failure_reason": "unsupported_item_type",
        }

    blob_path = item.get("content")
    if not blob_path:
        return None, {
            "source": "item_content",
            "item_type": item_type,
            "failure_reason": "missing_blob_path",
        }

    mime_type = (item_metadata.get("mimeType") or "").lower()
    filename = (item_metadata.get("fileName") or blob_path).lower()

    try:
        raw_bytes = read_blob_bytes(blob_path)
    except Exception as exc:
        logger.warning("Podcast source blob read failed for %s: %s", blob_path, exc)
        return None, {
            "source": "item_content",
            "item_type": item_type,
            "blob_path": blob_path,
            "mime_type": mime_type,
            "filename": filename,
            "failure_reason": f"blob_read_failed:{type(exc).__name__}",
        }

    if mime_type == "application/pdf" or filename.endswith(".pdf"):
        text = _truncate_text(_extract_pdf_text(raw_bytes))
        return text, {
            "source": "item_content",
            "item_type": item_type,
            "blob_path": blob_path,
            "mime_type": mime_type or "application/pdf",
            "filename": filename,
            "byte_length": len(raw_bytes),
            "text_length": len(text or ""),
            "failure_reason": None if text else "pdf_text_extraction_empty",
        }

    if mime_type.startswith("text/") or filename.endswith(".txt"):
        text = _truncate_text(raw_bytes.decode("utf-8", errors="ignore"))
        return text, {
            "source": "item_content",
            "item_type": item_type,
            "blob_path": blob_path,
            "mime_type": mime_type or "text/plain",
            "filename": filename,
            "byte_length": len(raw_bytes),
            "text_length": len(text or ""),
            "failure_reason": None if text else "text_blob_empty",
        }

    return None, {
        "source": "item_content",
        "item_type": item_type,
        "blob_path": blob_path,
        "mime_type": mime_type,
        "filename": filename,
        "failure_reason": "unsupported_file_type",
    }


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
    return _truncate_text_to_limit(text, MAX_PODCAST_TEXT_CHARS)


def _truncate_text_to_limit(text: Optional[str], max_chars: int) -> Optional[str]:
    if not text:
        return text
    cleaned = _clean_podcast_script_text(str(text))
    if len(cleaned) <= max_chars:
        return cleaned
    truncated = cleaned[:max_chars]
    return truncated.rsplit(" ", 1)[0]


def _truncate_intro_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return text
    cleaned = _clean_podcast_script_text(str(text))
    if len(cleaned) <= MAX_PODCAST_INTRO_CHARS:
        return cleaned
    truncated = cleaned[:MAX_PODCAST_INTRO_CHARS]
    return truncated.rsplit(" ", 1)[0]


def _safe_preview(text: Optional[str], max_chars: int) -> Optional[str]:
    if text is None:
        return None
    value = str(text)
    if len(value) <= max_chars:
        return value
    return value[:max_chars]


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


def _extract_remote_text(source_url: str) -> Optional[str]:
    text, _details = _extract_remote_text_with_diagnostics(source_url)
    return text


def _extract_remote_text_with_diagnostics(source_url: str) -> tuple[Optional[str], dict]:
    if not source_url:
        return None, {
            "source": "source_url",
            "failure_reason": "missing_source_url",
        }

    try:
        response = requests.get(
            source_url,
            timeout=PODCAST_FETCH_TIMEOUT_SECONDS,
            headers={"User-Agent": PODCAST_FETCH_USER_AGENT},
            allow_redirects=True,
        )
        response.raise_for_status()
    except requests.Timeout:
        return None, {
            "source": "source_url",
            "source_url": source_url,
            "failure_reason": "source_fetch_timeout",
        }
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        return None, {
            "source": "source_url",
            "source_url": source_url,
            "status_code": status_code,
            "failure_reason": f"source_fetch_http_{status_code or 'unknown'}",
        }
    except requests.RequestException as exc:
        return None, {
            "source": "source_url",
            "source_url": source_url,
            "failure_reason": f"source_fetch_request_error:{type(exc).__name__}",
        }
    except Exception as exc:
        return None, {
            "source": "source_url",
            "source_url": source_url,
            "failure_reason": f"source_fetch_unexpected_error:{type(exc).__name__}",
        }

    content_type = (response.headers.get("content-type") or "").lower()
    details = {
        "source": "source_url",
        "source_url": source_url,
        "final_url": response.url,
        "status_code": response.status_code,
        "content_type": content_type,
        "content_length": len(response.content or b""),
    }
    if "application/pdf" in content_type or source_url.lower().endswith(".pdf"):
        text = _truncate_text(_extract_pdf_text(response.content))
        details["text_length"] = len(text or "")
        details["failure_reason"] = None if text else "source_pdf_text_extraction_empty"
        return text, details

    text = _extract_html_text(response.text if response.text else response.content.decode("utf-8", errors="ignore"))
    text = _truncate_text(text)
    details["text_length"] = len(text or "")
    details["failure_reason"] = None if text else "source_html_text_extraction_empty"
    return text, details


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
