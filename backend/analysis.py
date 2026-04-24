import os
import logging
import base64
import mimetypes
import time
from functools import lru_cache
from pathlib import Path
from openai import OpenAI
from google import genai
from google.genai import types
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import storage

from tracing import create_span, record_exception

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", os.getenv("OPENROUTER_API_KEY", "ollama"))
OPENAI_MODEL = os.getenv("OPENAI_MODEL", os.getenv("OPENROUTER_MODEL", "gemma4:31b"))
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", os.getenv("OPENROUTER_BASE_URL", "http://nixos-gpt:11434/v1"))
# Use OpenAI's embedding model natively or fallback
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-2-preview")
GEMINI_EMBEDDING_MAX_RETRIES = max(0, int(os.getenv("GEMINI_EMBEDDING_MAX_RETRIES", "4")))
GEMINI_EMBEDDING_RETRY_BASE_DELAY = max(0.0, float(os.getenv("GEMINI_EMBEDDING_RETRY_BASE_DELAY", "2.0")))
GEMINI_EMBEDDING_INLINE_BYTES_LIMIT = max(
    1,
    int(os.getenv("GEMINI_EMBEDDING_INLINE_BYTES_LIMIT", str(20 * 1024 * 1024))),
)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
google_genai_client = None
if GOOGLE_API_KEY:
    try:
        google_genai_client = genai.Client(api_key=GOOGLE_API_KEY)
    except Exception as e:
        logger.error(f"Failed to initialize Google GenAI client: {e}")

client = None
if OPENAI_API_KEY:
    try:
        client = OpenAI(
            base_url=OPENAI_BASE_URL,
            api_key=OPENAI_API_KEY,
        )
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")

@lru_cache(maxsize=1)
def get_analysis_prompt():
    """Reads the analysis prompt from the prompts directory."""
    try:
        # Assuming the prompt file is located at ./prompts/analyze-this.md relative to backend/
        prompt_path = os.path.join(os.path.dirname(__file__), 'prompts', 'analyze-this.md')
        with open(prompt_path, 'r') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading prompt file: {e}")
        return "You are an AI assistant. Analyze this item."


def get_image_data_url(content: str) -> str | None:
    """
    Convert a storage path or URL to a data URL for image analysis.

    Args:
        content: Either a full URL (http/https) or a relative storage path

    Returns:
        A data URL (base64) or the original URL if already valid
    """
    # If it's already a full URL or data URL, return as-is
    if content.startswith(('http://', 'https://', 'data:')):
        return content

    # Otherwise, it's a relative storage path - fetch from Firebase Storage
    try:
        bucket = storage.bucket()
        blob = bucket.blob(content)

        if not blob.exists():
            logger.error(f"Blob does not exist: {content}")
            return None

        # Download the image bytes
        image_bytes = blob.download_as_bytes()

        # Determine MIME type from content type or file extension
        content_type = blob.content_type
        if not content_type:
            ext = os.path.splitext(content)[1].lower()
            mime_map = {
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
                '.webp': 'image/webp',
            }
            content_type = mime_map.get(ext, 'image/jpeg')

        # Encode as base64 data URL
        b64_data = base64.b64encode(image_bytes).decode('utf-8')
        return f"data:{content_type};base64,{b64_data}"

    except Exception as e:
        logger.error(f"Failed to fetch image from storage: {e}")
        return None


def _guess_mime_type(content: str | None, item_metadata: dict | None = None) -> str | None:
    if item_metadata:
        mime_type = item_metadata.get("mimeType") or item_metadata.get("mime_type")
        if mime_type:
            return str(mime_type)

    if not content:
        return None

    guessed, _ = mimetypes.guess_type(content)
    return guessed


def _read_storage_bytes(content: str) -> bytes | None:
    try:
        if os.getenv("APP_ENV") == "development":
            local_path = Path("static") / content
            if not local_path.exists():
                return None
            return local_path.read_bytes()

        bucket = storage.bucket()
        blob = bucket.blob(content)
        if not blob.exists():
            return None
        return blob.download_as_bytes()
    except Exception as e:
        logger.warning("Failed to read embedding media bytes for %s: %s", content, e)
        return None


def _decode_data_url(content: str) -> tuple[bytes, str] | None:
    if not content.startswith("data:"):
        return None

    try:
        header, encoded = content.split(",", 1)
        mime_type = header[5:].split(";", 1)[0] or "application/octet-stream"
        if ";base64" not in header:
            return None
        return base64.b64decode(encoded), mime_type
    except Exception:
        return None


def _build_multimodal_embedding_contents(
    text: str,
    *,
    item_type: str | None = None,
    content: str | None = None,
    item_metadata: dict | None = None,
    title: str | None = None,
):
    normalized_type = (item_type or "").lower()
    if normalized_type not in {"image", "screenshot", "audio", "video", "file"}:
        if title:
            return f"Title: {title}\nSummary: {text}"
        return text

    parts: list[types.Part] = []
    context_bits = []
    if title:
        context_bits.append(f"Title: {title}")
    if text:
        context_bits.append(f"Summary: {text}")
    if context_bits:
        parts.append(types.Part.from_text(text="\n".join(context_bits)))

    mime_type = _guess_mime_type(content, item_metadata)
    supported_media = False
    if normalized_type in {"image", "screenshot"}:
        supported_media = bool(mime_type and mime_type.startswith("image/"))
    elif normalized_type == "audio":
        supported_media = bool(mime_type and mime_type.startswith("audio/"))
    elif normalized_type == "video":
        supported_media = bool(mime_type and mime_type.startswith("video/"))
    elif normalized_type == "file":
        supported_media = mime_type in {"application/pdf", "text/plain"}

    if not supported_media or not content:
        return parts or text

    data_url = _decode_data_url(content)
    if data_url:
        raw_bytes, data_url_mime_type = data_url
        mime_type = data_url_mime_type
    elif content.startswith(("http://", "https://")):
        logger.info("Skipping multimodal embedding fetch for remote URL content: %s", content)
        return parts or text
    else:
        raw_bytes = _read_storage_bytes(content)

    if not raw_bytes:
        return parts or text

    if len(raw_bytes) > GEMINI_EMBEDDING_INLINE_BYTES_LIMIT:
        logger.warning(
            "Skipping inline embedding media for %s (%d bytes exceeds %d byte limit).",
            content,
            len(raw_bytes),
            GEMINI_EMBEDDING_INLINE_BYTES_LIMIT,
        )
        return parts or text

    parts.append(types.Part.from_bytes(data=raw_bytes, mime_type=mime_type))
    return parts

def build_analysis_prompt(preferred_tags: list[str] | None) -> str:
    prompt_text = get_analysis_prompt()
    if not preferred_tags:
        return prompt_text

    tag_lines = "\n".join([f"- {tag}" for tag in preferred_tags])
    tag_block = f"\n\nPreferred tags (use when appropriate):\n{tag_lines}\n"
    return prompt_text.rstrip() + tag_block


def analyze_content(content: str, item_type: str = 'text', preferred_tags: list[str] | None = None):
    """
    Analyzes the given content using OpenRouter and returns the structured JSON response.
    """
    if not client:
        logger.warning("OpenRouter client not initialized. Skipping analysis.")
        return None

    prompt_text = build_analysis_prompt(preferred_tags)
    
    messages = [{"role": "system", "content": prompt_text}]

    normalized_type = (item_type or 'text').lower()

    if normalized_type in ['image', 'screenshot']:
        # Convert storage path to data URL if needed
        image_url = get_image_data_url(content)
        if not image_url:
            logger.error(f"Could not resolve image URL for: {content}")
            return normalize_analysis({"error": f"Could not load image: {content}"})

        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": "Analyze this image item:"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_url
                    }
                }
            ]
        })
    elif normalized_type in ['web_url', 'weburl', 'media', 'video', 'audio', 'file']:
        # For non-image URLs, ask the model to analyze the content at the URL
        messages.append({"role": "user", "content": f"Analyze the content at this URL:\n\n{content}"})
    else:
        messages.append({"role": "user", "content": f"Analyze this user item:\n\n{content}"})

    # Trace the LLM API call
    with create_span("llm_api_call", {
        "llm.provider": "openai_compatible",
        "llm.model": OPENAI_MODEL,
        "llm.item_type": normalized_type,
        "llm.operation": "analysis",
    }) as llm_span:
        try:
            logger.info(f"Sending request to model: {OPENAI_MODEL}")
            completion = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                response_format={"type": "json_object"}
            )

            result_content = completion.choices[0].message.content
            logger.info("Received analysis result")

            # Add usage info if available
            if hasattr(completion, 'usage') and completion.usage:
                llm_span.set_attribute("llm.prompt_tokens", completion.usage.prompt_tokens or 0)
                llm_span.set_attribute("llm.completion_tokens", completion.usage.completion_tokens or 0)
                llm_span.set_attribute("llm.total_tokens", completion.usage.total_tokens or 0)

            llm_span.set_attribute("llm.response_length", len(result_content) if result_content else 0)

            # Depending on the response, it might be a string JSON, we need to return it as a dict if possible
            # but the caller will likely store it as is or parse it.
            # Let's try to parse it to ensure it's valid JSON
            import json
            try:
                parsed = json.loads(result_content)
                llm_span.set_attribute("llm.parse_success", True)
                result = normalize_analysis(parsed)
                # Record key analysis results
                if result.get('timeline'):
                    llm_span.set_attribute("llm.result.has_timeline", True)
                if result.get('follow_up'):
                    llm_span.set_attribute("llm.result.has_follow_up", True)
                return result
            except json.JSONDecodeError as json_err:
                logger.error("Failed to decode JSON from AI response")
                llm_span.set_attribute("llm.parse_success", False)
                record_exception(json_err)
                return normalize_analysis({"raw_analysis": result_content, "error": "Invalid JSON"})

        except Exception as e:
            logger.error(f"Error during analysis: {e}")
            llm_span.set_attribute("llm.api_error", str(e))
            record_exception(e)
            return normalize_analysis({"error": str(e)})


def generate_embedding(
    text: str,
    task_type: str = "RETRIEVAL_DOCUMENT",
    *,
    item_type: str | None = None,
    content: str | None = None,
    item_metadata: dict | None = None,
    title: str | None = None,
) -> list[float] | None:
    """
    Generates a vector embedding for the given text.
    """
    if not text:
        return None

    use_gemini_embeddings = "gemini" in EMBEDDING_MODEL

    if use_gemini_embeddings and not google_genai_client:
        logger.error(
            "Gemini embedding model '%s' requires GOOGLE_API_KEY, but no Google GenAI client is configured.",
            EMBEDDING_MODEL,
        )
        return None

    # Handle Gemini embeddings through the Google GenAI client.
    if use_gemini_embeddings and google_genai_client:
        embed_contents = _build_multimodal_embedding_contents(
            text,
            item_type=item_type,
            content=content,
            item_metadata=item_metadata,
            title=title,
        )
        for attempt in range(GEMINI_EMBEDDING_MAX_RETRIES + 1):
            try:
                logger.info(f"Generating Gemini embedding using model: {EMBEDDING_MODEL}, task_type: {task_type}")
                response = google_genai_client.models.embed_content(
                    model=EMBEDDING_MODEL,
                    contents=embed_contents,
                    config={
                        'task_type': task_type,
                        'output_dimensionality': 1536
                    }
                )
                if response and response.embeddings:
                    return response.embeddings[0].values
                return None
            except Exception as e:
                if attempt < GEMINI_EMBEDDING_MAX_RETRIES and _is_rate_limit_error(e):
                    delay = GEMINI_EMBEDDING_RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "Gemini embedding rate limited for model '%s'; retrying in %.1fs (attempt %d/%d).",
                        EMBEDDING_MODEL,
                        delay,
                        attempt + 1,
                        GEMINI_EMBEDDING_MAX_RETRIES,
                    )
                    time.sleep(delay)
                    continue

                logger.error(f"Failed to generate Gemini embedding: {e}")
                return None

    # Fallback to OpenAI compatible client
    if not client:
        return None

    try:
        # Truncate text if too long (rough check)
        if len(text) > 8000:
            text = text[:8000]

        logger.info(f"Generating OpenAI-compatible embedding using model: {EMBEDDING_MODEL}")
        response = client.embeddings.create(
            input=[text],
            model=EMBEDDING_MODEL
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        return None


def _is_rate_limit_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    code = getattr(exc, "code", None)
    message = str(exc).lower()
    return (
        status_code == 429
        or code == 429
        or "429" in message
        or "too many requests" in message
        or "rate limit" in message
    )


def _unwrap_analysis_payload(raw_response: dict) -> dict:
    """Flatten model responses that wrap the actual analysis in an item object."""
    if not isinstance(raw_response, dict):
        return raw_response

    item_payload = raw_response.get("item")
    if isinstance(item_payload, dict) and isinstance(item_payload.get("analysis"), dict):
        return dict(item_payload["analysis"])

    analysis_payload = raw_response.get("analysis")
    canonical_keys = {
        "overview",
        "timeline",
        "follow_up",
        "tags",
        "consumption_time_minutes",
        "podcast_candidate",
        "podcast_candidate_reason",
        "podcast_source_kind",
        "podcast_title",
        "podcast_summary",
        "error",
    }
    if isinstance(analysis_payload, dict) and not any(key in raw_response for key in canonical_keys):
        return dict(analysis_payload)

    return raw_response


def normalize_analysis(raw_response: dict) -> dict:
    """
    Normalizes AI analysis response to standard format.
    Ensures 'overview' field exists even if AI doesn't provide it.
    """
    raw_response = _unwrap_analysis_payload(raw_response)

    if not raw_response:
        return {
            "overview": "Analysis unavailable",
            "error": "Empty response",
            "podcast_candidate": False,
            "podcast_candidate_reason": "empty_response",
            "podcast_source_kind": "unsupported",
        }

    # If there's an error, preserve it but ensure overview exists
    if "error" in raw_response:
        raw_response.setdefault("overview", f"Error: {raw_response['error']}")
        raw_response.setdefault("podcast_candidate", False)
        raw_response.setdefault("podcast_candidate_reason", "analysis_error")
        raw_response.setdefault("podcast_source_kind", "unsupported")
        return raw_response

    # Ensure overview exists - generate from other fields if missing
    if "overview" not in raw_response or not raw_response["overview"]:
        # Try to generate overview from available fields
        if "timeline" in raw_response:
            timeline_value = raw_response["timeline"]
            if isinstance(timeline_value, list):
                timeline_value = timeline_value[0] if timeline_value else {}
            if not isinstance(timeline_value, dict):
                timeline_value = {}
            raw_response["overview"] = f"Timeline event identified: {timeline_value.get('principal', 'Unknown')} at {timeline_value.get('location', 'Unknown location')}"
        elif "follow_up" in raw_response:
            raw_response["overview"] = f"Follow up required: {raw_response['follow_up']}"
        elif "step" in raw_response:
             raw_response["overview"] = f"Suggested action: {raw_response['step']}"
             # Legacy support cleanup if needed, but 'action' is removed from model so maybe just leave it in dict for now or ignore.
        elif "details" in raw_response:
             raw_response["overview"] = str(raw_response["details"])[:200]
        else:
             raw_response["overview"] = "Content analyzed - no specific action identified"

    raw_response.setdefault("podcast_candidate", False)
    raw_response.setdefault("podcast_candidate_reason", None)
    raw_response.setdefault("podcast_source_kind", None)
    raw_response.setdefault("podcast_title", None)
    raw_response.setdefault("podcast_summary", raw_response.get("overview"))

    return raw_response
