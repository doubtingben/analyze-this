import os
import argparse
import asyncio
import logging
from dotenv import load_dotenv

from analysis import analyze_content
from notifications import format_item_message, send_irccat_message
from database import DatabaseInterface, FirestoreDatabase, SQLiteDatabase
from worker_queue import process_queue_jobs
from tracing import create_span, add_span_attributes, add_span_event, record_exception

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

    tags_by_user = {}
    user_emails = {data.get('user_email') for data in docs_to_process if data.get('user_email')}
    for email in user_emails:
        tags_by_user[email] = await db.get_user_tags(email)

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
            preferred_tags = tags_by_user.get(data.get('user_email'))
            analysis_result = await loop.run_in_executor(None, analyze_content, content, item_type, preferred_tags)

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
                message = format_item_message(
                    "analyzed",
                    data.get('user_email') or "unknown",
                    doc_id,
                    data.get('title'),
                    detail=f"status={new_status}"
                )
                await send_irccat_message(message)
                if new_status in ("timeline", "follow_up"):
                    event = "added to timeline" if new_status == "timeline" else "marked for follow up"
                    follow_message = format_item_message(
                        event,
                        data.get('user_email') or "unknown",
                        doc_id,
                        data.get('title')
                    )
                    await send_irccat_message(follow_message)
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

async def _process_analysis_item(db, data, context):
    doc_id = data.get('firestore_id') or data.get('id')
    user_email = data.get('user_email')
    preferred_tags = None
    if context and user_email:
        preferred_tags = context.get('tags_by_user', {}).get(user_email)

    # Add tracing attributes
    add_span_attributes({
        "analysis.item_id": doc_id,
        "analysis.user_email": user_email or "unknown",
    })

    # 1. Mark as Analyzing
    with create_span("update_status_analyzing", {"item.id": doc_id}) as status_span:
        try:
            await db.update_shared_item(doc_id, {'status': 'analyzing'})
            status_span.set_attribute("status.updated", True)
        except Exception as e:
            logger.error(f"Failed to update status to analyzing for {doc_id}: {e}")
            status_span.set_attribute("status.updated", False)
            record_exception(e)

    content = data.get('content')
    item_type = data.get('type', 'text')

    add_span_attributes({
        "analysis.item_type": item_type,
        "analysis.has_content": content is not None,
    })

    if not content:
        logger.warning(f"Item {doc_id} has no content. Skipping.")
        add_span_event("skipped_no_content", {"item_id": doc_id})
        await db.update_shared_item(doc_id, {'status': 'processed', 'next_step': 'no_content'})
        return True, None

    try:
        # Run LLM analysis
        with create_span("llm_content_analysis", {"item.id": doc_id, "item.type": item_type}) as llm_span:
            loop = asyncio.get_running_loop()
            analysis_result = await loop.run_in_executor(None, analyze_content, content, item_type, preferred_tags)

            if analysis_result and not analysis_result.get('error'):
                llm_span.set_attribute("analysis.success", True)
                new_status = 'analyzed'
                if analysis_result.get('timeline'):
                    new_status = 'timeline'
                    llm_span.set_attribute("analysis.has_timeline", True)
                elif analysis_result.get('follow_up'):
                    new_status = 'follow_up'
                    llm_span.set_attribute("analysis.has_follow_up", True)
                llm_span.set_attribute("analysis.new_status", new_status)
            else:
                llm_span.set_attribute("analysis.success", False)
                if analysis_result:
                    llm_span.set_attribute("analysis.error", analysis_result.get('error', 'Unknown'))

        if analysis_result and not analysis_result.get('error'):
            # Save results
            with create_span("save_analysis_result", {"item.id": doc_id}) as save_span:
                await db.update_shared_item(doc_id, {
                    'analysis': analysis_result,
                    'status': new_status,
                    'next_step': new_status
                })
                save_span.set_attribute("save.status", new_status)

            logger.info(f"Successfully analyzed item {doc_id}.")
            add_span_event("analysis_completed", {"item_id": doc_id, "status": new_status})

            message = format_item_message(
                "analyzed",
                data.get('user_email') or "unknown",
                doc_id,
                data.get('title'),
                detail=f"status={new_status}"
            )
            await send_irccat_message(message)
            if new_status in ("timeline", "follow_up"):
                event = "added to timeline" if new_status == "timeline" else "marked for follow up"
                follow_message = format_item_message(
                    event,
                    data.get('user_email') or "unknown",
                    doc_id,
                    data.get('title')
                )
                await send_irccat_message(follow_message)
            return True, None

        error_msg = "Unknown error"
        if analysis_result:
            error_msg = analysis_result.get('error', error_msg)

        logger.warning(f"Analysis failed for item {doc_id}: {error_msg}")
        add_span_event("analysis_failed", {"item_id": doc_id, "error": error_msg})
        await db.update_shared_item(doc_id, {
            'status': 'error',
            'next_step': 'error',
            'analysis': analysis_result
        })
        return False, f"analysis_failed: {error_msg}"
    except Exception as e:
        logger.error(f"Failed to analyze item {doc_id}: {e}")
        record_exception(e)
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
        async def prepare_tags(db, jobs):
            user_emails = {job.get('user_email') for job in jobs if job.get('user_email')}
            tags_by_user = {}
            for email in user_emails:
                tags_by_user[email] = await db.get_user_tags(email)
            return {"tags_by_user": tags_by_user}

        asyncio.run(process_queue_jobs(
            job_type="analysis",
            limit=args.limit,
            lease_seconds=args.lease_seconds,
            get_db=get_db,
            process_item_fn=_process_analysis_item,
            logger=logger,
            halt_on_error=False,
            prepare_fn=prepare_tags,
            continuous=args.loop,
        ))
        return

    asyncio.run(process_items_async(limit=args.limit, item_id=args.id, force=args.force))


if __name__ == "__main__":
    main()
