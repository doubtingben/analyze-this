import os
import logging
import httpx

logger = logging.getLogger(__name__)

IRCCAT_URL = os.getenv("IRCCAT_URL", "https://irccat.interestedparticipant.org/send")
IRCCAT_TIMEOUT = float(os.getenv("IRCCAT_TIMEOUT", "2.5"))
IRCCAT_ENABLED = os.getenv("IRCCAT_ENABLED", "true").lower() in ("1", "true", "yes")
IRCCAT_MAX_LEN = int(os.getenv("IRCCAT_MAX_LEN", "400"))
IRCCAT_BEARER_TOKEN = (os.getenv("IRCCAT_BEARER_TOKEN") or "").strip()

# IRC formatting
BOLD = "\x02"
COLOR = "\x03"
RESET = "\x0F"

# mIRC color numbers
_CLR_BLUE = "02"
_CLR_GREEN = "03"
_CLR_RED = "04"
_CLR_PURPLE = "06"
_CLR_ORANGE = "07"
_CLR_TEAL = "10"
_CLR_GREY = "14"

_EVENT_COLORS = {
    "shared": _CLR_BLUE,
    "analyzed": _CLR_GREEN,
    "normalized": _CLR_TEAL,
    "marked for follow up": _CLR_PURPLE,
    "deleted via follow-up": _CLR_RED,
    "archived via follow-up": _CLR_ORANGE,
    "archived with context": _CLR_ORANGE,
    "updated via follow-up": _CLR_GREEN,
}


def _compact_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).split())


def format_item_message(event: str, user_email: str, item_id: str, title: str | None, detail: str | None = None) -> str:
    safe_title = _compact_text(title) or "(untitled)"
    short_id = item_id[:8] if item_id else "?"
    user = user_email.split("@")[0] if user_email else "unknown"

    color = _EVENT_COLORS.get(event, _CLR_GREY)
    if "failed" in event:
        color = _CLR_RED

    parts = [
        f"{BOLD}{COLOR}{color}{event}{RESET}",
        f"\"{safe_title}\"",
    ]
    detail_text = _compact_text(detail)
    if detail_text:
        parts.append(detail_text)
    parts.append(user)
    parts.append(f"{COLOR}{_CLR_GREY}{short_id}{RESET}")

    base = " | ".join(parts)
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
