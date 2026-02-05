import os
import argparse
import asyncio
import logging
from dotenv import load_dotenv

from normalization import normalize_item_title
from database import DatabaseInterface, FirestoreDatabase, SQLiteDatabase
from worker_analysis import get_db
from worker_queue import process_queue_jobs

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

async def process_normalization_async(limit: int = 10, item_id: str = None, force: bool = False, allow_missing_analysis: bool = False):
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
        if force:
            logger.info(f"Querying for up to {limit} NORMALIZED items to RE-normalize...")
            docs_to_process = await db.get_normalized_items(limit)
        else:
            logger.info(f"Querying for up to {limit} unnormalized items...")
            docs_to_process = await db.get_unnormalized_items(limit)
            
        logger.info(f"Found {len(docs_to_process)} items to process.")

    for data in docs_to_process:
        doc_id = data.get('firestore_id')
        current_title = data.get('title')
        content = data.get('content')
        item_type = data.get('type', 'text')
        analysis_data = data.get('analysis')

        if not analysis_data and not allow_missing_analysis:
            logger.info(f"Skipping item {doc_id}: Analysis is missing and --allow-no-analysis is not set.")
            continue
        
        logger.info(f"Normalizing item {doc_id} ('{current_title}')...")
        
        try:
            # We run normalization in executor since it calls sync network (OpenAI client)
            loop = asyncio.get_running_loop()
            new_title = await loop.run_in_executor(None, normalize_item_title, content, item_type, current_title, analysis_data)
            
            updates = {'is_normalized': True}
            
            if new_title:
                if new_title != current_title:
                    logger.info(f"Title changed: '{current_title}' -> '{new_title}'")
                    updates['title'] = new_title
                else:
                    logger.info("Title unchanged.")
            else:
                logger.warning(f"Normalization returned None/Failed for {doc_id}. Marking as error.")
                updates['status'] = 'error'
            
            await db.update_shared_item(doc_id, updates)
            logger.info(f"Successfully updated processing for item {doc_id}.")
                
        except Exception as e:
            logger.critical(f"FATAL: Failed to normalize item {doc_id}. internal error: {e}")
            # Identify if this is a prompt loading error or other critical failure not handled within normalize_item_title
            # We raise here to halt the worker as requested.
            raise e

async def _process_normalize_item(db, data, context, allow_missing_analysis=False):
    doc_id = data.get('firestore_id') or data.get('id')
    current_title = data.get('title')
    content = data.get('content')
    item_type = data.get('type', 'text')
    analysis_data = data.get('analysis')

    if not analysis_data and not allow_missing_analysis:
        logger.warning(f"Skipping item {doc_id}: Analysis is missing and --allow-no-analysis is not set. Marking as failed (will retry).")
        return False, "missing_analysis"

    loop = asyncio.get_running_loop()
    new_title = await loop.run_in_executor(None, normalize_item_title, content, item_type, current_title, analysis_data)

    updates = {'is_normalized': True}
    if new_title:
        if new_title != current_title:
            logger.info(f"Title changed: '{current_title}' -> '{new_title}'")
            updates['title'] = new_title
        else:
            logger.info("Title unchanged.")
        
        await db.update_shared_item(doc_id, updates)
        logger.info(f"Successfully normalized item {doc_id}.")
        return True, None
    else:
        logger.warning(f"Normalization returned None/Failed for {doc_id}. Marking as error.")
        updates['status'] = 'error'
        await db.update_shared_item(doc_id, updates)
        return False, "normalization_returned_none"

def main():
    parser = argparse.ArgumentParser(description="Worker to normalize titles of shared items.")
    parser.add_argument("--limit", type=int, default=10, help="Number of items to process (default: 10)")
    parser.add_argument("--id", type=str, help="Specific Item ID to process")
    parser.add_argument("--force", action="store_true", help="Force re-normalization (works with --id or batch mode)")
    parser.add_argument("--queue", action="store_true", help="Process jobs from the worker queue")
    parser.add_argument("--lease-seconds", type=int, default=600, help="Lease duration for queued jobs (seconds)")
    parser.add_argument("--loop", action="store_true", help="Run in continuous loop mode (only with --queue)")
    parser.add_argument("--allow-no-analysis", action="store_true", help="Allow validation even if analysis data is missing")
    
    args = parser.parse_args()
    
    if args.queue:
        from functools import partial
        
        async def run_queue_mode():
            # Automatically retry items that failed due to "missing_analysis"
            # This ensures that if we have fixed the logic or the data, they get processed.
            try:
                db_instance = await get_db()
                count = await db_instance.reset_failed_jobs('normalize', 'missing_analysis')
                if count > 0:
                    logger.info(f"Reset {count} failed jobs with 'missing_analysis' error to 'queued' state.")
            except Exception as e:
                logger.warning(f"Failed to reset failed jobs: {e}")

            process_fn = partial(_process_normalize_item, allow_missing_analysis=args.allow_no_analysis)
            
            await process_queue_jobs(
                job_type="normalize",
                limit=args.limit,
                lease_seconds=args.lease_seconds,
                get_db=get_db,
                process_item_fn=process_fn,
                logger=logger,
                halt_on_error=True,
                continuous=args.loop,
            )

        asyncio.run(run_queue_mode())
        return

    asyncio.run(process_normalization_async(
        limit=args.limit, 
        item_id=args.id, 
        force=args.force, 
        allow_missing_analysis=args.allow_no_analysis
    ))

if __name__ == "__main__":
    main()
