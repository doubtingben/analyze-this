import os
import argparse
import asyncio
import logging
from dotenv import load_dotenv

from analysis import analyze_content
from database import DatabaseInterface, FirestoreDatabase, SQLiteDatabase
from worker_queue import process_queue_jobs

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
APP_ENV = os.getenv("APP_ENV", "production")


async def get_db() -> DatabaseInterface:
    if APP_ENV == "development":
        logger.info("Using SQLiteDatabase")
        db = SQLiteDatabase()
        if hasattr(db, 'init_db'):
            await db.init_db()
        return db
    else:
        logger.info("Using FirestoreDatabase")
        return FirestoreDatabase()


async def process_items_async(limit: int = 10, item_id: str = None, force: bool = False):
    """
    Processes unanalyzed items using DatabaseInterface.
    """
    db = await get_db()

    docs_to_process = []

    if item_id:
        # Fetch specific document
        logger.info(f"Fetching specific item with ID: {item_id}")
        data = await db.get_shared_item(item_id)
        if data:
            # If force is True OR analysis is missing, process it
            if force or not data.get('analysis'):
                 docs_to_process.append(data)
            else:
                logger.info(f"Item {item_id} already has analysis. Use --force to re-analyze.")
        else:
            logger.error(f"Item {item_id} not found.")
    else:
        logger.info(f"Querying for up to {limit} new items...")
        docs_to_process = await db.get_items_by_status("new", limit)
        logger.info(f"Found {len(docs_to_process)} items to process.")

    for data in docs_to_process:
        doc_id = data.get('firestore_id')
        logger.info(f"Processing item {doc_id} ({data.get('type')})...")

        # 1. Mark as Analyzing
        try:
             await db.update_shared_item(doc_id, {'status': 'analyzing'})
        except Exception as e:
             logger.error(f"Failed to update status to analyzing for {doc_id}: {e}")

        content = data.get('content')
        item_type = data.get('type', 'text')

        if not content:
            logger.warning(f"Item {doc_id} has no content. Skipping.")
            await db.update_shared_item(doc_id, {'status': 'processed', 'next_step': 'no_content'})
            continue

        try:
            # Note: analyze_content is synchronous or async? from analysis.py
            # assuming sync for now based on original valid code
            # But we are in async function.
            # Ideally analysis should be async or run in executor.

            loop = asyncio.get_running_loop()
            # If analyze_content is CPU bound blocking:
            analysis_result = await loop.run_in_executor(None, analyze_content, content, item_type)

            if analysis_result and not analysis_result.get('error'):
                # Determine status based on analysis result content
                new_status = 'analyzed'  # Default fallback
                if analysis_result.get('timeline'):
                    new_status = 'timeline'
                elif analysis_result.get('follow_up'):
                    new_status = 'follow_up'

                # Update DB
                await db.update_shared_item(doc_id, {
                    'analysis': analysis_result,
                    'status': new_status,
                    'next_step': new_status
                })
                logger.info(f"Successfully analyzed item {doc_id}.")
            else:
                error_msg = "Unknown error"
                if analysis_result:
                    error_msg = analysis_result.get('error', error_msg)
                
                logger.warning(f"Analysis failed for item {doc_id}: {error_msg}")
                await db.update_shared_item(doc_id, {
                    'status': 'error', 
                    'next_step': 'error',
                    'analysis': analysis_result  # Save the error details if available
                })

        except Exception as e:
            logger.error(f"Failed to analyze item {doc_id}: {e}")
            await db.update_shared_item(doc_id, {'status': 'error', 'next_step': 'error'})

async def _process_analysis_item(db, data):
    doc_id = data.get('firestore_id') or data.get('id')

    # 1. Mark as Analyzing
    try:
        await db.update_shared_item(doc_id, {'status': 'analyzing'})
    except Exception as e:
        logger.error(f"Failed to update status to analyzing for {doc_id}: {e}")

    content = data.get('content')
    item_type = data.get('type', 'text')

    if not content:
        logger.warning(f"Item {doc_id} has no content. Skipping.")
        await db.update_shared_item(doc_id, {'status': 'processed', 'next_step': 'no_content'})
        return True, None

    try:
        loop = asyncio.get_running_loop()
        analysis_result = await loop.run_in_executor(None, analyze_content, content, item_type)

        if analysis_result and not analysis_result.get('error'):
            new_status = 'analyzed'
            if analysis_result.get('timeline'):
                new_status = 'timeline'
            elif analysis_result.get('follow_up'):
                new_status = 'follow_up'

            await db.update_shared_item(doc_id, {
                'analysis': analysis_result,
                'status': new_status,
                'next_step': new_status
            })
            logger.info(f"Successfully analyzed item {doc_id}.")
            return True, None

        error_msg = "Unknown error"
        if analysis_result:
            error_msg = analysis_result.get('error', error_msg)
            
        logger.warning(f"Analysis failed for item {doc_id}: {error_msg}")
        await db.update_shared_item(doc_id, {
            'status': 'error', 
            'next_step': 'error',
            'analysis': analysis_result
        })
        return False, f"analysis_failed: {error_msg}"
    except Exception as e:
        logger.error(f"Failed to analyze item {doc_id}: {e}")
        await db.update_shared_item(doc_id, {'status': 'error', 'next_step': 'error'})
        return False, str(e)

def main():
    parser = argparse.ArgumentParser(description="Worker to process unanalyzed shared items.")
    parser.add_argument("--limit", type=int, default=10, help="Number of items to process (default: 10)")
    parser.add_argument("--id", type=str, help="Specific Item ID to process")
    parser.add_argument("--force", action="store_true", help="Force re-analysis if ID is provided")
    parser.add_argument("--queue", action="store_true", help="Process jobs from the worker queue")
    parser.add_argument("--lease-seconds", type=int, default=600, help="Lease duration for queued jobs (seconds)")
    parser.add_argument("--loop", action="store_true", help="Run in continuous loop mode (only with --queue)")

    args = parser.parse_args()

    if args.queue:
        asyncio.run(process_queue_jobs(
            job_type="analysis",
            limit=args.limit,
            lease_seconds=args.lease_seconds,
            get_db=get_db,
            process_item_fn=_process_analysis_item,
            logger=logger,
            halt_on_error=False,
            continuous=args.loop,
        ))
        return

    asyncio.run(process_items_async(limit=args.limit, item_id=args.id, force=args.force))


if __name__ == "__main__":
    main()
