import os
import argparse
import asyncio
import datetime
import logging
import zoneinfo
from dotenv import load_dotenv

from database import DatabaseInterface, FirestoreDatabase, SQLiteDatabase
from worker_queue import start_health_check_server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
APP_ENV = os.getenv("APP_ENV", "production")

MANAGER_INTERVAL_SECONDS = int(os.getenv("MANAGER_INTERVAL_SECONDS", "60"))

# Cloud Run Job launching configuration
ENABLE_JOB_LAUNCHING = os.getenv("ENABLE_JOB_LAUNCHING", "false").lower() == "true"
GCP_PROJECT = os.getenv("GCP_PROJECT", "analyze-this-2026")
GCP_REGION = os.getenv("GCP_REGION", "us-central1")

# Map job types to Cloud Run Job names
JOB_TYPE_TO_JOB_NAME = {
    "analysis": "worker-analysis",
    "normalize": "worker-normalize",
    "follow_up": "worker-follow-up",
}


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


# --- Manager Rules ---
# Each rule is an async function that takes (db, logger) and returns the number
# of jobs it acted on. Add new rules to MANAGER_RULES to extend the manager.


async def rule_retry_single_attempt_failures(db: DatabaseInterface, logger: logging.Logger) -> int:
    """Reset failed jobs that have only been attempted once back to queued."""
    jobs = await db.get_failed_worker_jobs(max_attempts=1)

    if not jobs:
        return 0

    reset_count = 0
    for job in jobs:
        job_id = job.get('firestore_id') or job.get('id')
        job_type = job.get('job_type', 'unknown')
        item_id = job.get('item_id', 'unknown')
        error = job.get('error', '')
        attempts = job.get('attempts', 0)

        logger.info(
            f"Retrying job {job_id} (type={job_type}, item={item_id}, "
            f"attempts={attempts}, error={error})"
        )

        success = await db.reset_worker_job(job_id)
        if success:
            reset_count += 1
        else:
            logger.warning(f"Failed to reset job {job_id}")

    return reset_count


async def rule_reset_missing_analysis_failures(db: DatabaseInterface, logger: logging.Logger) -> int:
    """Reset normalize jobs that failed due to missing_analysis back to queued."""
    count = await db.reset_failed_jobs('normalize', 'missing_analysis')
    return count


async def rule_create_timeline_follow_ups(db: DatabaseInterface, logger: logging.Logger) -> int:
    """Create follow-up prompts for timeline events whose dates have passed."""
    items = await db.get_items_by_status('timeline', limit=100)
    if not items:
        return 0

    count = 0
    for item in items:
        doc_id = item.get('firestore_id') or item.get('id')
        analysis = item.get('analysis') or {}
        timeline = analysis.get('timeline') or {}
        date_str = timeline.get('date')

        if not date_str:
            continue

        # Parse event date
        try:
            event_date = datetime.date.fromisoformat(date_str)
        except (ValueError, TypeError):
            logger.warning(f"Item {doc_id}: invalid timeline date '{date_str}'. Skipping.")
            continue

        # Determine "today" in the user's timezone
        user_email = item.get('user_email')
        user_tz_name = "America/New_York"  # default
        if user_email:
            try:
                user = await db.get_user(user_email)
                if user and user.timezone:
                    user_tz_name = user.timezone
            except Exception:
                pass

        try:
            user_tz = zoneinfo.ZoneInfo(user_tz_name)
        except Exception:
            user_tz = zoneinfo.ZoneInfo("America/New_York")

        today = datetime.datetime.now(user_tz).date()

        if event_date >= today:
            continue  # Event hasn't happened yet

        # Build follow-up question
        title = item.get('title') or analysis.get('overview') or 'this event'
        location = timeline.get('location')
        question_parts = [f'How was "{title}"?']
        if location:
            question_parts.append(f"Did you make it to {location}?")
        question_parts.append("Anything to note or report?")
        follow_up_question = " ".join(question_parts)

        # Update item: status -> follow_up, add follow_up question to analysis
        updated_analysis = dict(analysis)
        updated_analysis['follow_up'] = follow_up_question

        await db.update_shared_item(doc_id, {
            'status': 'follow_up',
            'analysis': updated_analysis,
        })

        logger.info(f"Created follow-up for past timeline event {doc_id} (date={date_str})")
        count += 1

    return count


async def rule_launch_worker_jobs(db: DatabaseInterface, logger: logging.Logger) -> int:
    """Check for queued work and launch Cloud Run Jobs on demand."""
    if not ENABLE_JOB_LAUNCHING:
        logger.debug("Job launching disabled (ENABLE_JOB_LAUNCHING != true). Skipping.")
        return 0

    counts = await db.get_queued_job_counts_by_type()
    if not counts:
        return 0

    logger.info(f"Queued job counts: {counts}")

    launched = 0
    loop = asyncio.get_running_loop()

    for job_type, queued_count in counts.items():
        if queued_count <= 0:
            continue

        job_name = JOB_TYPE_TO_JOB_NAME.get(job_type)
        if not job_name:
            logger.warning(f"Unknown job type '{job_type}' with {queued_count} queued jobs. Skipping.")
            continue

        try:
            already_running = await loop.run_in_executor(None, _is_job_running, job_name)
            if already_running:
                logger.info(f"Job '{job_name}' already has an active execution. Skipping launch.")
                continue

            logger.info(f"Launching Cloud Run Job '{job_name}' for {queued_count} queued {job_type} jobs...")
            await loop.run_in_executor(None, _run_job, job_name)
            launched += 1
            logger.info(f"Successfully launched '{job_name}'.")
        except Exception as e:
            logger.error(f"Failed to launch job '{job_name}': {e}")

    return launched


def _is_job_running(job_name: str) -> bool:
    """Check if a Cloud Run Job has an active (running) execution."""
    from google.cloud.run_v2 import ExecutionsClient
    from google.cloud.run_v2.types import ListExecutionsRequest

    client = ExecutionsClient()
    parent = f"projects/{GCP_PROJECT}/locations/{GCP_REGION}/jobs/{job_name}"

    request = ListExecutionsRequest(parent=parent)
    executions = client.list_executions(request=request)

    for execution in executions:
        # Check if execution is still running (not completed/failed)
        if not execution.completion_time:
            return True

    return False


def _run_job(job_name: str) -> None:
    """Launch a Cloud Run Job execution."""
    from google.cloud.run_v2 import JobsClient
    from google.cloud.run_v2.types import RunJobRequest

    client = JobsClient()
    name = f"projects/{GCP_PROJECT}/locations/{GCP_REGION}/jobs/{job_name}"

    request = RunJobRequest(name=name)
    client.run_job(request=request)


# Registry of all manager rules. Add new rules here.
MANAGER_RULES = [
    ("retry_single_attempt_failures", rule_retry_single_attempt_failures),
    ("reset_missing_analysis_failures", rule_reset_missing_analysis_failures),
    ("create_timeline_follow_ups", rule_create_timeline_follow_ups),
    ("launch_worker_jobs", rule_launch_worker_jobs),
]


async def run_manager_cycle(db: DatabaseInterface):
    """Execute all manager rules once."""
    logger.info("Starting manager cycle...")

    for rule_name, rule_fn in MANAGER_RULES:
        try:
            count = await rule_fn(db, logger)
            if count > 0:
                logger.info(f"Rule '{rule_name}' acted on {count} job(s).")
            else:
                logger.debug(f"Rule '{rule_name}' found nothing to do.")
        except Exception as e:
            logger.error(f"Rule '{rule_name}' failed: {e}")

    logger.info("Manager cycle complete.")


async def run_manager(continuous: bool = False):
    """Main manager loop."""
    db = await get_db()

    logger.info(
        f"Worker Manager started. Interval: {MANAGER_INTERVAL_SECONDS}s. "
        f"Continuous: {continuous}. Rules: {len(MANAGER_RULES)}. "
        f"Job launching: {ENABLE_JOB_LAUNCHING}"
    )

    if continuous:
        asyncio.create_task(start_health_check_server())

    while True:
        await run_manager_cycle(db)

        if not continuous:
            logger.info("Single run complete. Exiting.")
            return

        logger.info(f"Sleeping {MANAGER_INTERVAL_SECONDS}s until next cycle...")
        await asyncio.sleep(MANAGER_INTERVAL_SECONDS)


def main():
    global MANAGER_INTERVAL_SECONDS

    parser = argparse.ArgumentParser(description="Worker Manager - evaluates and retries failed jobs.")
    parser.add_argument("--loop", action="store_true", help="Run in continuous loop mode")
    parser.add_argument(
        "--interval", type=int, default=None,
        help=f"Interval between cycles in seconds (default: {MANAGER_INTERVAL_SECONDS})"
    )

    args = parser.parse_args()

    if args.interval is not None:
        MANAGER_INTERVAL_SECONDS = args.interval

    asyncio.run(run_manager(continuous=args.loop))


if __name__ == "__main__":
    main()
