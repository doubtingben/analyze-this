import os
import logging
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
def get_analysis_prompt():
    """Reads the analysis prompt from the prompts directory."""
    try:
        # Assuming the prompt file is located at ../prompts/analyze-this.md relative to backend/
        prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'prompts', 'analyze-this.md')
        with open(prompt_path, 'r') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading prompt file: {e}")
        return "You are an AI assistant. Analyze this item."

def analyze_content(content: str, item_type: str = 'text'):
    """
    Analyzes the given content using OpenRouter and returns the structured JSON response.
    """
    if not client:
        logger.warning("OpenRouter client not initialized. Skipping analysis.")
        return None

    prompt_text = get_analysis_prompt()
    
    messages = [{"role": "system", "content": prompt_text}]

    normalized_type = (item_type or 'text').lower()

    if normalized_type in ['image', 'screenshot']:
        # Assuming content is a URL pointing to an image
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": "Analyze this image item:"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": content
                    }
                }
            ]
        })
    elif normalized_type in ['web_url', 'weburl', 'media', 'video', 'audio', 'file']:
        # For non-image URLs, ask the model to analyze the content at the URL
        messages.append({"role": "user", "content": f"Analyze the content at this URL:\n\n{content}"})
    else:
        messages.append({"role": "user", "content": f"Analyze this user item:\n\n{content}"})

    try:
        logger.info(f"Sending request to OpenRouter model: {OPENROUTER_MODEL}")
        completion = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        result_content = completion.choices[0].message.content
        logger.info("Received analysis result")
        
        # Depending on the response, it might be a string JSON, we need to return it as a dict if possible
        # but the caller will likely store it as is or parse it.
        # Let's try to parse it to ensure it's valid JSON
        import json
        try:
            return json.loads(result_content)
        except json.JSONDecodeError:
            logger.error("Failed to decode JSON from AI response")
            return {"raw_analysis": result_content, "error": "Invalid JSON"}

    except Exception as e:
        logger.error(f"Error during analysis: {e}")
        return {"error": str(e)}
