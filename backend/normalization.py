import os
import logging
import json
import base64
from functools import lru_cache
from openai import OpenAI
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import storage

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
        # Resolve path relative to this file: ./prompts/normalize-this.md
        base_path = Path(__file__).resolve().parent
        prompt_path = base_path / 'prompts' / 'normalize-this.md'
        
        with open(prompt_path, 'r') as f:
            return f.read()
    except Exception as e:
        logger.critical(f"FATAL: Error reading prompt file: {e}")
        raise e

def get_image_data_url(content: str) -> str | None:
    """
    Convert a storage path or URL to a data URL for image analysis.
    """
    # If it's already a full URL or data URL, return as-is
    if content.startswith(('http://', 'https://', 'data:')):
        return content

    # Otherwise, it's a relative storage path - fetch from Firebase Storage
    try:
        # Check if firebase app is initialized
        if not firebase_admin._apps:
             # Basic initialization if not tied to a specific bucket config yet, 
             # though typically the worker initializes this.
             # We assume worker_normalize has initialized the app with storageBucket.
             pass

        bucket = storage.bucket()
        blob = bucket.blob(content)

        if not blob.exists():
            logger.error(f"Blob does not exist: {content}")
            return None

        # Download the image bytes
        image_bytes = blob.download_as_bytes()

        # Determine MIME type
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

def normalize_item_title(content: str, item_type: str = 'text', current_title: str = None, analysis_data: dict = None) -> str | None:
    """
    Normalizes the title of an item using OpenRouter.
    Returns the new title string, or None if normalization failed or no change needed (implied by returning same title).
    """
    if not client:
        logger.warning("OpenRouter client not initialized. Skipping normalization.")
        return None

    # This will raise if the prompt file is missing/unreadable, propagating the error up.
    prompt_text = get_normalization_prompt()
    
    # Construct the user message
    context_text = ""
    if current_title:
        context_text += f"Current Title: {current_title}\n"
    if analysis_data:
        context_text += f"Analysis Data: {json.dumps(analysis_data, default=str)}\n"
    context_text += f"Type: {item_type}"

    if item_type in ['image', 'screenshot']:
        # Resolve image URL
        image_url = get_image_data_url(content)
        if not image_url:
            logger.error(f"Could not resolve image URL for content: {content}")
            # Fallback to text mode? Or fail? failing is safer.
            return None

        messages = [
            {"role": "system", "content": prompt_text},
            {
                "role": "user", 
                "content": [
                    {"type": "text", "text": context_text},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ]
    else:
        user_content = f"Content: {content}\n{context_text}"
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
            
            new_title = parsed.get("title") or parsed.get("item.title") or parsed.get("normalized_title")
            
            if not new_title and "item" in parsed:
                 new_title = parsed["item"].get("title")

            if new_title:
                return str(new_title)
            
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
