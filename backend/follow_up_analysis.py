import os
import json
import logging
from functools import lru_cache
from openai import OpenAI
from dotenv import load_dotenv

from analysis import normalize_analysis

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

    try:
        logger.info(f"Sending follow-up analysis request to OpenRouter model: {OPENROUTER_MODEL}")
        completion = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=messages,
            response_format={"type": "json_object"}
        )

        result_content = completion.choices[0].message.content
        logger.info("Received follow-up analysis result")

        try:
            parsed = json.loads(result_content)
            return normalize_analysis(parsed)
        except json.JSONDecodeError:
            logger.error("Failed to decode JSON from AI response")
            return normalize_analysis({"raw_analysis": result_content, "error": "Invalid JSON"})

    except Exception as e:
        logger.error(f"Error during follow-up analysis: {e}")
        return normalize_analysis({"error": str(e)})
