import os
import argparse
import asyncio
import logging
from dotenv import load_dotenv

from follow_up_analysis import analyze_follow_up
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


async def _process_follow_up_item(db, data, context):
    """Process a single follow-up job from the worker queue."""
    doc_id = data.get('firestore_id') or data.get('id')
    user_email = data.get('user_email')
    preferred_tags = None
    if context and user_email:
        preferred_tags = context.get('tags_by_user', {}).get(user_email)

    # Fetch the item
    item = await db.get_shared_item(doc_id)
    if not item:
        logger.warning(f"Item {doc_id} not found. Skipping.")
        return False, f"item_not_found: {doc_id}"

    # Verify item has follow_up status and analysis with follow_up field
    analysis = item.get('analysis') or {}
    follow_up_question = analysis.get('follow_up')
    if not follow_up_question:
        logger.info(f"Item {doc_id} has no follow_up question. Skipping.")
        return True, None  # Not an error, just nothing to do

    # Fetch follow-up notes
    follow_up_notes = await db.get_follow_up_notes(doc_id)
    if not follow_up_notes:
        logger.info(f"Item {doc_id} has no follow-up notes yet. Skipping.")
        return False, "no_follow_up_notes"

    content = item.get('content', '')
    item_type = item.get('type', 'text')

    logger.info(f"Re-analyzing item {doc_id} with {len(follow_up_notes)} follow-up note(s)...")

    try:
        loop = asyncio.get_running_loop()
        analysis_result = await loop.run_in_executor(
            None, analyze_follow_up, content, item_type, analysis, follow_up_notes, preferred_tags
        )

        if analysis_result and not analysis_result.get('error'):
            # Determine new status based on analysis result
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
            logger.info(f"Successfully re-analyzed item {doc_id}. New status: {new_status}")
            return True, None

        error_msg = "Unknown error"
        if analysis_result:
            error_msg = analysis_result.get('error', error_msg)

        logger.warning(f"Follow-up analysis failed for item {doc_id}: {error_msg}")
        return False, f"analysis_failed: {error_msg}"

    except Exception as e:
        logger.error(f"Failed to re-analyze item {doc_id}: {e}")
        return False, str(e)


def main():
    parser = argparse.ArgumentParser(description="Worker to re-analyze items with follow-up notes.")
    parser.add_argument("--limit", type=int, default=10, help="Number of items to process (default: 10)")
    parser.add_argument("--queue", action="store_true", help="Process jobs from the worker queue")
    parser.add_argument("--lease-seconds", type=int, default=600, help="Lease duration for queued jobs (seconds)")
    parser.add_argument("--loop", action="store_true", help="Run in continuous loop mode (only with --queue)")

    args = parser.parse_args()

    if args.queue:
        async def prepare_tags(db, jobs):
            user_emails = {job.get('user_email') for job in jobs if job.get('user_email')}
            tags_by_user = {}
            for email in user_emails:
                tags_by_user[email] = await db.get_user_tags(email)
            return {"tags_by_user": tags_by_user}

        asyncio.run(process_queue_jobs(
            job_type="follow_up",
            limit=args.limit,
            lease_seconds=args.lease_seconds,
            get_db=get_db,
            process_item_fn=_process_follow_up_item,
            logger=logger,
            halt_on_error=False,
            prepare_fn=prepare_tags,
            continuous=args.loop,
        ))
        return

    # Without --queue, nothing to do (follow-up only works via queue)
    logger.info("Use --queue to process follow-up jobs from the worker queue.")


if __name__ == "__main__":
    main()
