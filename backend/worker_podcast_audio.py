import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

from analysis import normalize_analysis
from podcast_audio import get_podcast_audio_driver
from podcast_content import (
    build_podcast_notes,
    build_podcast_script,
    build_shared_item_url,
    normalize_audio_bytes,
    resolve_episode_content,
    upload_audio_bytes,
)
from tracing import add_span_attributes, create_span, record_exception
from worker_analysis import get_db


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()


def _audio_extension(mime_type: str | None) -> str:
    if mime_type == "audio/wav":
        return "wav"
    if mime_type == "audio/ogg":
        return "ogg"
    return "mp3"


async def _process_podcast_audio_item(db, data, context):
    item_id = data.get("firestore_id") or data.get("id")
    user_email = data.get("user_email")
    analysis = normalize_analysis(data.get("analysis") or {})
    add_span_attributes({
        "podcast.item_id": item_id,
        "podcast.user_email": user_email or "unknown",
        "podcast.item_type": data.get("type") or "unknown",
    })

    if not item_id or not user_email:
        return False, "missing_item_context"

    feed_entry = await db.get_podcast_feed_entry_by_item(user_email, item_id)
    if not feed_entry:
        return False, "missing_feed_entry"

    feed_entry_id = feed_entry.get("firestore_id") or feed_entry.get("id")
    if not feed_entry_id:
        return False, "missing_feed_entry_id"

    await db.update_podcast_feed_entry(feed_entry_id, {
        "status": "processing",
        "error": None,
        "updated_at": datetime.now(timezone.utc),
    })

    source_kind = analysis.get("podcast_source_kind") or feed_entry.get("source_kind") or "unsupported"
    if source_kind == "unsupported":
        await db.update_podcast_feed_entry(feed_entry_id, {
            "status": "failed",
            "error": "unsupported_type",
            "updated_at": datetime.now(timezone.utc),
        })
        return False, "unsupported_type"

    driver = get_podcast_audio_driver()
    episode = None

    try:
        with create_span("generate_podcast_audio", {"item.id": item_id, "podcast.source_kind": source_kind}):
            if source_kind == "native_audio":
                result = await driver.normalize_source_audio(source_item=data, metadata={"item_id": item_id})
                script_text = None
                resolved_source_kind = source_kind
            else:
                episode = resolve_episode_content(data, analysis)
                logger.info(
                    "Resolved podcast episode content for item %s: body_source=%s retrieval_error=%s details=%s",
                    item_id,
                    episode.body_source,
                    episode.retrieval_error,
                    episode.retrieval_details,
                )
                script_text = build_podcast_script(data, analysis, episode)
                if not script_text:
                    raise RuntimeError("text_extraction_failed")
                resolved_source_kind = episode.body_source
                result = await driver.synthesize_speech(
                    text=script_text,
                    title=feed_entry.get("title") or data.get("title"),
                    voice_id=None,
                    metadata={"item_id": item_id},
                )

        normalized_audio_bytes, normalized_mime_type = normalize_audio_bytes(result.audio_bytes or b"", result.mime_type)
        blob_path = f"uploads/{user_email}/podcast/{item_id}-{uuid4().hex}.{_audio_extension(normalized_mime_type)}"
        upload_audio_bytes(blob_path, normalized_audio_bytes, normalized_mime_type)

        await db.update_podcast_feed_entry(feed_entry_id, {
            "status": "ready",
            "audio_storage_path": blob_path,
            "duration_seconds": result.duration_seconds,
            "mime_type": normalized_mime_type,
            "provider": result.provider,
            "provider_voice_id": os.getenv("ELEVENLABS_VOICE_ID"),
            "source_kind": resolved_source_kind,
            "script_text": script_text,
            "analysis_notes": build_podcast_notes(data, analysis),
            "shared_item_url": build_shared_item_url(item_id),
            "debug_source_retrieval_error": episode.retrieval_error if source_kind != "native_audio" else None,
            "debug_source_retrieval_details": episode.retrieval_details if source_kind != "native_audio" else None,
            "error": None,
            "updated_at": datetime.now(timezone.utc),
            "published_at": datetime.now(timezone.utc),
        })
        return True, None
    except Exception as exc:
        logger.exception("Podcast audio processing failed for item %s", item_id)
        record_exception(exc)
        await db.update_podcast_feed_entry(feed_entry_id, {
            "status": "failed",
            "error": str(exc),
            "debug_source_retrieval_error": episode.retrieval_error if episode else None,
            "debug_source_retrieval_details": episode.retrieval_details if episode else None,
            "updated_at": datetime.now(timezone.utc),
        })
        return False, str(exc)
