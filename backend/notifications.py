import os
import logging
import httpx

logger = logging.getLogger(__name__)

IRCCAT_URL = os.getenv("IRCCAT_URL", "https://chat.interestedparticipant.org/send")
IRCCAT_TIMEOUT = float(os.getenv("IRCCAT_TIMEOUT", "2.5"))
IRCCAT_ENABLED = os.getenv("IRCCAT_ENABLED", "true").lower() in ("1", "true", "yes")
IRCCAT_MAX_LEN = int(os.getenv("IRCCAT_MAX_LEN", "400"))
IRCCAT_BEARER_TOKEN = (os.getenv("IRCCAT_BEARER_TOKEN") or "").strip()


def _compact_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).split())


def format_item_message(event: str, user_email: str, item_id: str, title: str | None, detail: str | None = None) -> str:
    safe_title = _compact_text(title) or "(untitled)"
    base = f"AnalyzeThis: {user_email} {event} \"{safe_title}\" (id={item_id})"
    detail_text = _compact_text(detail)
    if detail_text:
        base = f"{base} — {detail_text}"
    if len(base) > IRCCAT_MAX_LEN:
        base = base[: IRCCAT_MAX_LEN - 1] + "…"
    return base


async def send_irccat_message(message: str) -> None:
    if not IRCCAT_ENABLED:
        return
    if not IRCCAT_URL:
        logger.warning("IRCCAT_URL is not set; skipping notification")
        return

    try:
        headers = {}
        if IRCCAT_BEARER_TOKEN:
            headers["Authorization"] = f"Bearer {IRCCAT_BEARER_TOKEN}"
        async with httpx.AsyncClient(timeout=IRCCAT_TIMEOUT) as client:
            await client.post(IRCCAT_URL, content=message.encode("utf-8"), headers=headers)
    except Exception as exc:
        logger.warning("Failed to send irccat notification: %s", exc)
