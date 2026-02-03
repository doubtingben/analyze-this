import os
import argparse
import asyncio
import logging
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

MANAGER_INTERVAL_SECONDS = int(os.getenv("MANAGER_INTERVAL_SECONDS", "300"))  # 5 minutes


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


# Registry of all manager rules. Add new rules here.
MANAGER_RULES = [
    ("retry_single_attempt_failures", rule_retry_single_attempt_failures),
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
        f"Continuous: {continuous}. Rules: {len(MANAGER_RULES)}"
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
    parser = argparse.ArgumentParser(description="Worker Manager - evaluates and retries failed jobs.")
    parser.add_argument("--loop", action="store_true", help="Run in continuous loop mode")
    parser.add_argument(
        "--interval", type=int, default=None,
        help=f"Interval between cycles in seconds (default: {MANAGER_INTERVAL_SECONDS})"
    )

    args = parser.parse_args()

    if args.interval is not None:
        global MANAGER_INTERVAL_SECONDS
        MANAGER_INTERVAL_SECONDS = args.interval

    asyncio.run(run_manager(continuous=args.loop))


if __name__ == "__main__":
    main()
