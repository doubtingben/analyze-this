import argparse
import asyncio
import datetime
import functools
import logging
import os
import re
import socket
import urllib.parse
import ipaddress
import uuid
from pathlib import Path
from typing import Optional

import firebase_admin
import httpx
from dotenv import load_dotenv
from firebase_admin import storage

from analysis import client as openrouter_client, OPENROUTER_MODEL
from audio_synthesis import get_tts_provider
from models import PodcastEpisode
from podcast_derivative import is_narrative_or_technical
from tracing import create_span, add_span_event, record_exception
from worker_analysis import get_db
from worker_queue import process_queue_jobs

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

APP_ENV = os.getenv("APP_ENV", "production")
MAX_SOURCE_TEXT_CHARS = int(os.getenv("PODCAST_SOURCE_TEXT_MAX", "12000"))
MAX_TTS_CHUNK_CHARS = int(os.getenv("PODCAST_TTS_CHUNK_MAX", "1800"))


if not firebase_admin._apps:
    firebase_admin.initialize_app(options={
        'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET')
    })


def _clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<script[\\s\\S]*?</script>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<style[\\s\\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _chunk_text(text: str, max_chars: int = MAX_TTS_CHUNK_CHARS) -> list[str]:
    normalized = _clean_text(text)
    if len(normalized) <= max_chars:
        return [normalized]

    chunks: list[str] = []
    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= max_chars:
            current = f"{current} {sentence}".strip()
            continue

        if current:
            chunks.append(current)
            current = ""

        while len(sentence) > max_chars:
            chunks.append(sentence[:max_chars])
            sentence = sentence[max_chars:]

        current = sentence

    if current:
        chunks.append(current)

    return [c for c in chunks if c]


def _read_local_user_file(blob_path: str, user_email: str) -> Optional[bytes]:
    base_dir = Path("static").resolve()
    requested_path = (base_dir / blob_path).resolve()
    if not str(requested_path).startswith(str(base_dir)):
        return None

    expected_prefix = f"uploads/{user_email}/"
    if not blob_path.startswith(expected_prefix):
        return None

    if not requested_path.exists() or not requested_path.is_file():
        return None

    return requested_path.read_bytes()


def _download_user_blob(blob_path: str, user_email: str) -> Optional[bytes]:
    if not blob_path:
        return None

    if ".." in blob_path or blob_path.startswith("/") or "\\" in blob_path:
        return None

    expected_prefix = f"uploads/{user_email}/"
    if not blob_path.startswith(expected_prefix):
        return None

    if APP_ENV == "development":
        return _read_local_user_file(blob_path, user_email)

    bucket = storage.bucket()
    blob = bucket.blob(blob_path)
    if not blob.exists():
        return None

    return blob.download_as_bytes()


def _extract_pdf_text_safe(file_bytes: bytes) -> str:
    # Safe extractor path: optional dependency usage with graceful fallback.
    try:
        from pypdf import PdfReader  # type: ignore

        import io
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)
    except Exception:
        # Last-resort fallback (lossy): decode what can be decoded.
        return file_bytes.decode("utf-8", errors="ignore")


def _is_safe_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        ip = socket.gethostbyname(hostname)
        ip_obj = ipaddress.ip_address(ip)

        if (ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or
            ip_obj.is_multicast or ip_obj.is_unspecified or str(ip_obj) == "0.0.0.0"):
            return False

        return True
    except Exception:
        return False


def _fetch_url_text(url: str) -> str:
    try:
        current_url = url
        max_redirects = 5
        redirect_count = 0

        while redirect_count <= max_redirects:
            if not _is_safe_url(current_url):
                logger.warning("Blocked attempt to fetch unsafe URL: %s", current_url)
                return ""

            response = httpx.get(current_url, timeout=20.0, follow_redirects=False)

            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get('location')
                if not location:
                    break
                current_url = urllib.parse.urljoin(current_url, location)
                redirect_count += 1
                continue

            response.raise_for_status()
            content_type = response.headers.get("content-type", "")

            if "application/pdf" in content_type:
                return _extract_pdf_text_safe(response.content)

            return _clean_text(response.text)

        logger.warning("Too many redirects for %s", url)
        return ""
    except Exception as e:
        logger.warning("Failed to fetch URL text for %s: %s", url, e)
        return ""


def _build_narration_script(source_text: str, item_title: str | None) -> str:
    source_text = _clean_text(source_text)[:MAX_SOURCE_TEXT_CHARS]
    if not source_text:
        return ""

    if openrouter_client:
        try:
            completion = openrouter_client.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a podcast narration writer. Produce a clean, spoken-word script "
                            "with short sections and smooth transitions. Avoid markdown and stage directions."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Title: {item_title or 'Untitled'}\n\n"
                            "Create a 4-8 minute narration script from the following source text. "
                            "Keep factual details and remove boilerplate.\n\n"
                            f"{source_text}"
                        ),
                    },
                ],
            )
            script = (completion.choices[0].message.content or "").strip()
            if script:
                return script
        except Exception as e:
            logger.warning("Failed to generate narration script via OpenRouter: %s", e)

    return source_text


def _upload_audio_bytes(audio_bytes: bytes, user_email: str) -> str:
    file_name = f"podcast-{uuid.uuid4()}.mp3"
    blob_name_relative = f"uploads/{user_email}/podcasts/{file_name}"

    if APP_ENV == "development":
        local_path = Path("static") / blob_name_relative
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(audio_bytes)
        return blob_name_relative

    bucket = storage.bucket()
    blob = bucket.blob(blob_name_relative)
    blob.upload_from_string(audio_bytes, content_type="audio/mpeg")
    return blob_name_relative


def _extract_source_text(data: dict) -> str:
    item_type = (data.get("type") or "").lower()
    content = data.get("content") or ""
    metadata = data.get("item_metadata") or {}

    if item_type in ("text",):
        return str(content)

    if item_type in ("web_url", "weburl") and isinstance(content, str) and content.startswith(("http://", "https://")):
        fetched = _fetch_url_text(content)
        if fetched:
            return fetched

    if item_type == "file":
        user_email = data.get("user_email") or ""
        if isinstance(content, str) and content.startswith("uploads/") and user_email:
            file_bytes = _download_user_blob(content, user_email)
            if file_bytes:
                file_name = str(metadata.get("fileName") or "").lower()
                mime_type = str(metadata.get("mimeType") or "").lower()
                if file_name.endswith(".pdf") or "pdf" in mime_type:
                    extracted = _extract_pdf_text_safe(file_bytes)
                else:
                    extracted = file_bytes.decode("utf-8", errors="ignore")
                if extracted:
                    return extracted

    for key in ("text", "summary", "description", "excerpt"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value

    return str(content) if isinstance(content, str) else ""


async def _process_podcast_derivative_item(db, data, context):
    doc_id = data.get('firestore_id') or data.get('id')
    user_email = data.get('user_email')
    item_type = (data.get('type') or '').lower()

    with create_span("process_podcast_derivative", {
        "podcast.item_id": doc_id,
        "podcast.user_email": user_email or "unknown",
        "podcast.item_type": item_type,
    }):
        if not doc_id or not user_email:
            return False, "missing_item_id_or_user"

        existing_episodes = await db.get_podcast_episodes(doc_id)
        if existing_episodes:
            logger.info("Item %s already has %s podcast episode(s). Skipping.", doc_id, len(existing_episodes))
            return True, None

        if item_type == "audio":
            audio_path = data.get("content")
            if not isinstance(audio_path, str) or not audio_path:
                return False, "missing_audio_content_path"

            episode = PodcastEpisode(
                item_id=doc_id,
                user_email=user_email,
                title=data.get("title"),
                source_type="existing_audio",
                script_text=None,
                audio_path=audio_path,
                tts_provider=None,
                tts_model=None,
                created_at=datetime.datetime.now(datetime.timezone.utc),
            )
            await db.create_podcast_episode(episode)
            add_span_event("podcast_episode_registered", {"item_id": doc_id, "source_type": "existing_audio"})
            return True, None

        if item_type not in ("file", "web_url", "weburl", "text"):
            return False, "ineligible_item_type"

        analysis = data.get("analysis") or {}
        if not is_narrative_or_technical(analysis):
            return False, "ineligible_classification"

        source_text = _extract_source_text(data)
        source_text = _clean_text(source_text)
        if not source_text:
            return False, "empty_source_text"

        narration_script = _build_narration_script(source_text, data.get("title"))
        chunks = _chunk_text(narration_script)
        if not chunks:
            return False, "empty_narration_script"

        provider = get_tts_provider()

        loop = asyncio.get_running_loop()
        audio_parts: list[bytes] = []

        for chunk in chunks:
            try:
                part = await loop.run_in_executor(None, provider.synthesize, chunk)
                if part:
                    audio_parts.append(part)
            except Exception as e:
                logger.error("TTS synthesis failed for item %s: %s", doc_id, e)
                record_exception(e)
                return False, f"tts_failed: {e}"

        if not audio_parts:
            return False, "tts_no_audio_generated"

        final_audio = b"".join(audio_parts)

        try:
            audio_path = await loop.run_in_executor(None, functools.partial(_upload_audio_bytes, final_audio, user_email))
        except Exception as e:
            logger.error("Failed to upload synthesized audio for %s: %s", doc_id, e)
            record_exception(e)
            return False, f"audio_upload_failed: {e}"

        episode = PodcastEpisode(
            item_id=doc_id,
            user_email=user_email,
            title=data.get("title"),
            source_type="generated",
            script_text=narration_script[:20000],
            audio_path=audio_path,
            tts_provider=provider.name,
            tts_model=provider.model,
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
        await db.create_podcast_episode(episode)

        add_span_event("podcast_episode_created", {
            "item_id": doc_id,
            "provider": provider.name,
            "model": provider.model,
            "audio_path": audio_path,
        })

        return True, None


def main():
    parser = argparse.ArgumentParser(description="Worker to create podcast derivative episodes.")
    parser.add_argument("--limit", type=int, default=10, help="Number of queued jobs to process (default: 10)")
    parser.add_argument("--lease-seconds", type=int, default=600, help="Lease duration for queued jobs (seconds)")

    args = parser.parse_args()

    asyncio.run(process_queue_jobs(
        job_type="podcast_derivative",
        limit=args.limit,
        lease_seconds=args.lease_seconds,
        get_db=get_db,
        process_item_fn=_process_podcast_derivative_item,
        logger=logger,
        halt_on_error=False,
        prepare_fn=None,
        continuous=False,
    ))


if __name__ == "__main__":
    main()
