import os
import argparse
import asyncio
import logging
from dotenv import load_dotenv

from normalization import normalize_item_title
from database import DatabaseInterface, FirestoreDatabase, SQLiteDatabase
from worker_analysis import get_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

async def process_normalization_async(limit: int = 10, item_id: str = None, force: bool = False):
    """
    Processes unnormalized items using DatabaseInterface.
    """
    db = await get_db()
    
    docs_to_process = []

    if item_id:
        # Fetch specific document
        logger.info(f"Fetching specific item with ID: {item_id}")
        data = await db.get_shared_item(item_id)
        if data:
            if force or not data.get('is_normalized'):
                 docs_to_process.append(data)
            else:
                logger.info(f"Item {item_id} is already normalized. Use --force to re-normalize.")
        else:
            logger.error(f"Item {item_id} not found.")
    else:
        logger.info(f"Querying for up to {limit} unnormalized items...")
        docs_to_process = await db.get_unnormalized_items(limit)
        logger.info(f"Found {len(docs_to_process)} items to process.")

    for data in docs_to_process:
        doc_id = data.get('firestore_id')
        current_title = data.get('title')
        content = data.get('content')
        item_type = data.get('type', 'text')
        
        logger.info(f"Normalizing item {doc_id} ('{current_title}')...")
        
        try:
            # We run normalization in executor since it calls sync network (OpenAI client)
            loop = asyncio.get_running_loop()
            new_title = await loop.run_in_executor(None, normalize_item_title, content, item_type, current_title)
            
            updates = {'is_normalized': True}
            
            if new_title:
                if new_title != current_title:
                    logger.info(f"Title changed: '{current_title}' -> '{new_title}'")
                    updates['title'] = new_title
                else:
                    logger.info("Title unchanged.")
            else:
                logger.warning(f"Normalization returned None/Failed for {doc_id}. Marking as normalized to prevent infinite loop.")
            
            await db.update_shared_item(doc_id, updates)
            logger.info(f"Successfully updated processing for item {doc_id}.")
                
        except Exception as e:
            logger.critical(f"FATAL: Failed to normalize item {doc_id}. internal error: {e}")
            # Identify if this is a prompt loading error or other critical failure not handled within normalize_item_title
            # We raise here to halt the worker as requested.
            raise e

def main():
    parser = argparse.ArgumentParser(description="Worker to normalize titles of shared items.")
    parser.add_argument("--limit", type=int, default=10, help="Number of items to process (default: 10)")
    parser.add_argument("--id", type=str, help="Specific Item ID to process")
    parser.add_argument("--force", action="store_true", help="Force re-normalization if ID is provided")
    
    args = parser.parse_args()
    
    asyncio.run(process_normalization_async(limit=args.limit, item_id=args.id, force=args.force))

if __name__ == "__main__":
    main()
