import os
import logging
import base64
from functools import lru_cache
from openai import OpenAI
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import storage

from tracing import create_span, record_exception

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free")

client = None
if OPENROUTER_API_KEY:
    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
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
    with create_span("openrouter_api_call", {
        "llm.provider": "openrouter",
        "llm.model": OPENROUTER_MODEL,
        "llm.item_type": normalized_type,
        "llm.operation": "analysis",
    }) as llm_span:
        try:
            logger.info(f"Sending request to OpenRouter model: {OPENROUTER_MODEL}")
            completion = client.chat.completions.create(
                model=OPENROUTER_MODEL,
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


def normalize_analysis(raw_response: dict) -> dict:
    """
    Normalizes AI analysis response to standard format.
    Ensures 'overview' field exists even if AI doesn't provide it.
    """
    if not raw_response:
        return {"overview": "Analysis unavailable", "error": "Empty response"}

    # If there's an error, preserve it but ensure overview exists
    if "error" in raw_response:
        raw_response.setdefault("overview", f"Error: {raw_response['error']}")
        return raw_response

    # Ensure overview exists - generate from other fields if missing
    if "overview" not in raw_response or not raw_response["overview"]:
        # Try to generate overview from available fields
        if "timeline" in raw_response:
            raw_response["overview"] = f"Timeline event identified: {raw_response['timeline'].get('principal', 'Unknown')} at {raw_response['timeline'].get('location', 'Unknown location')}"
        elif "follow_up" in raw_response:
            raw_response["overview"] = f"Follow up required: {raw_response['follow_up']}"
        elif "step" in raw_response:
             raw_response["overview"] = f"Suggested action: {raw_response['step']}"
             # Legacy support cleanup if needed, but 'action' is removed from model so maybe just leave it in dict for now or ignore.
        elif "details" in raw_response:
             raw_response["overview"] = str(raw_response["details"])[:200]
        else:
             raw_response["overview"] = "Content analyzed - no specific action identified"

    return raw_response
