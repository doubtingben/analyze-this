import os
import json
import logging
from functools import lru_cache
from openai import OpenAI
from dotenv import load_dotenv

from analysis import normalize_analysis
from tracing import create_span, add_span_attributes, record_exception

load_dotenv()

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
def get_follow_up_prompt():
    """Reads the follow-up prompt from the prompts directory."""
    try:
        prompt_path = os.path.join(os.path.dirname(__file__), 'prompts', 'follow-up.md')
        with open(prompt_path, 'r') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading follow-up prompt file: {e}")
        return "You are an AI assistant. Re-analyze this item with the additional context provided."


def build_follow_up_prompt(preferred_tags: list[str] | None) -> str:
    prompt_text = get_follow_up_prompt()
    if not preferred_tags:
        return prompt_text

    tag_lines = "\n".join([f"- {tag}" for tag in preferred_tags])
    tag_block = f"\n\nPreferred tags (use when appropriate):\n{tag_lines}\n"
    return prompt_text.rstrip() + tag_block


def analyze_follow_up(content: str, item_type: str, original_analysis: dict, follow_up_notes: list[dict], preferred_tags: list[str] | None = None):
    """
    Re-analyzes an item using original content, analysis, and follow-up notes.
    """
    if not client:
        logger.warning("OpenRouter client not initialized. Skipping follow-up analysis.")
        return None

    prompt_text = build_follow_up_prompt(preferred_tags)

    messages = [{"role": "system", "content": prompt_text}]

    # Build the user message with all context
    user_content = f"## Original Item ({item_type})\n\n{content}\n\n"
    user_content += f"## Original Analysis\n\n{json.dumps(original_analysis, indent=2)}\n\n"
    user_content += "## Follow-up Notes\n\n"
    for note in follow_up_notes:
        note_text = note.get('text', '')
        if note_text:
            user_content += f"- {note_text}\n"

    messages.append({"role": "user", "content": user_content})

    # Trace the LLM API call
    with create_span("openrouter_api_call", {
        "llm.provider": "openrouter",
        "llm.model": OPENROUTER_MODEL,
        "llm.item_type": item_type,
        "llm.notes_count": len(follow_up_notes),
        "llm.has_preferred_tags": preferred_tags is not None,
    }) as llm_span:
        try:
            logger.info(f"Sending follow-up analysis request to OpenRouter model: {OPENROUTER_MODEL}")
            completion = client.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=messages,
                response_format={"type": "json_object"}
            )

            result_content = completion.choices[0].message.content
            logger.info("Received follow-up analysis result")

            # Add usage info if available
            if hasattr(completion, 'usage') and completion.usage:
                llm_span.set_attribute("llm.prompt_tokens", completion.usage.prompt_tokens or 0)
                llm_span.set_attribute("llm.completion_tokens", completion.usage.completion_tokens or 0)
                llm_span.set_attribute("llm.total_tokens", completion.usage.total_tokens or 0)

            llm_span.set_attribute("llm.response_length", len(result_content) if result_content else 0)

            try:
                parsed = json.loads(result_content)
                llm_span.set_attribute("llm.parse_success", True)

                # Handle new format with 'action'
                if 'action' in parsed:
                    llm_span.set_attribute("llm.action", parsed.get('action', 'unknown'))
                    if parsed.get('analysis'):
                        parsed['analysis'] = normalize_analysis(parsed['analysis'])
                    return parsed

                # Legacy/Fallback format (treat as update/analysis only)
                llm_span.set_attribute("llm.action", "update")
                llm_span.set_attribute("llm.format", "legacy")
                normalized = normalize_analysis(parsed)
                return {
                    "action": "update",
                    "reasoning": "Legacy format received",
                    "analysis": normalized
                }

            except json.JSONDecodeError as json_err:
                logger.error("Failed to decode JSON from AI response")
                llm_span.set_attribute("llm.parse_success", False)
                llm_span.set_attribute("llm.parse_error", "json_decode_error")
                record_exception(json_err)
                return {
                    "action": "update",
                    "reasoning": "JSON Decode Error",
                    "analysis": normalize_analysis({"raw_analysis": result_content, "error": "Invalid JSON"})
                }

        except Exception as e:
            logger.error(f"Error during follow-up analysis: {e}")
            llm_span.set_attribute("llm.api_error", str(e))
            record_exception(e)
            return {
                "action": "update",
                "reasoning": f"Exception: {str(e)}",
                "analysis": normalize_analysis({"error": str(e)})
            }
