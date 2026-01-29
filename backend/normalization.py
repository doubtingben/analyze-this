import os
import logging
import json
from functools import lru_cache
from openai import OpenAI
from dotenv import load_dotenv

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
def get_normalization_prompt():
    """Reads the normalization prompt from the prompts directory."""
    try:
        from pathlib import Path
        # Resolve path relative to this file: ../prompts/normalize-this.md
        # This file is in backend/normalization.py -> parent is backend -> parent is root -> prompts -> file
        base_path = Path(__file__).resolve().parent.parent
        prompt_path = base_path / 'prompts' / 'normalize-this.md'
        
        with open(prompt_path, 'r') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading prompt file: {e}")
        return "You are a user agent tasked with normalizing media snippets shared by users."

def normalize_item_title(content: str, item_type: str = 'text', current_title: str = None) -> str | None:
    """
    Normalizes the title of an item using OpenRouter.
    Returns the new title string, or None if normalization failed or no change needed (implied by returning same title).
    """
    if not client:
        logger.warning("OpenRouter client not initialized. Skipping normalization.")
        return None

    prompt_text = get_normalization_prompt()
    
    # Construct the user message
    user_content = f"Content: {content}\n"
    if current_title:
        user_content += f"Current Title: {current_title}\n"
    user_content += f"Type: {item_type}"

    messages = [
        {"role": "system", "content": prompt_text},
        {"role": "user", "content": user_content}
    ]

    try:
        logger.info(f"Sending normalization request to OpenRouter model: {OPENROUTER_MODEL}")
        completion = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        result_content = completion.choices[0].message.content
        logger.info("Received normalization result")
        
        try:
            parsed = json.loads(result_content)
            # The prompt says "The field on the item that is being normalized is 'item.title'".
            # We expect the JSON to likely have a 'title' or 'item.title' key, or maybe just the object.
            # Let's assume the LLM follows instructions to output JSON.
            # We will look for 'title', 'item.title', or just take the whole thing if it's a string (though we requested json object).
            
            new_title = parsed.get("title") or parsed.get("item.title") or parsed.get("normalized_title")
            
            # If the model returns the whole object structure
            if not new_title and "item" in parsed:
                 new_title = parsed["item"].get("title")

            if new_title:
                return str(new_title)
            
            # Fallback: if single key in json
            if len(parsed) == 1:
                return str(list(parsed.values())[0])
                
            logger.warning(f"Could not extract title from response: {result_content}")
            return None

        except json.JSONDecodeError:
            logger.error("Failed to decode JSON from AI response")
            return None

    except Exception as e:
        logger.error(f"Error during normalization: {e}")
        return None
