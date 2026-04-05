import os
from pathlib import Path
from typing import Optional

import firebase_admin
from firebase_admin import storage


APP_ENV = os.getenv("APP_ENV", "production")
PUBLIC_APP_URL = (os.getenv("PUBLIC_APP_URL") or "").rstrip("/")
MAX_PODCAST_TEXT_CHARS = int(os.getenv("MAX_PODCAST_TEXT_CHARS", "12000"))


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

    return f"{title}\n\n{body}".strip()


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
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= MAX_PODCAST_TEXT_CHARS:
        return cleaned
    return cleaned[:MAX_PODCAST_TEXT_CHARS].rsplit(" ", 1)[0]


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
