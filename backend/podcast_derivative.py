from typing import Any


ELIGIBLE_DERIVATIVE_TYPES = {"audio", "file", "web_url", "weburl", "text"}


def is_narrative_or_technical(analysis: dict[str, Any] | None) -> bool:
    if not isinstance(analysis, dict):
        return False

    tags = analysis.get("tags") or []
    if isinstance(tags, list):
        lowered = {str(tag).strip().lower() for tag in tags if str(tag).strip()}
        if "narrative" in lowered or "technical" in lowered:
            return True

    overview = str(analysis.get("overview") or "").lower()
    return "narrative" in overview or "technical" in overview


def should_enqueue_podcast_derivative(item_type: str | None, analysis: dict[str, Any] | None = None) -> bool:
    normalized_type = (item_type or "").strip().lower()

    if normalized_type == "audio":
        return True

    if normalized_type not in ELIGIBLE_DERIVATIVE_TYPES:
        return False

    return is_narrative_or_technical(analysis)
