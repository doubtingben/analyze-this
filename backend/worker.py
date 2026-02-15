"""
Consolidated worker entry point for Cloud Run Jobs.

Usage:
    python worker.py --job-type analysis [--limit 20] [--lease-seconds 600]
    python worker.py --job-type normalize [--limit 20] [--lease-seconds 600]
    python worker.py --job-type follow_up [--limit 20] [--lease-seconds 600]

Dispatches to the appropriate processor function from the existing worker modules.
Runs in batch mode (process available jobs, then exit) - no health check server needed.
"""

import argparse
import asyncio
import logging
from functools import partial

from dotenv import load_dotenv

from worker_analysis import get_db, _process_analysis_item
from worker_normalize import _process_normalize_item
from worker_follow_up import _process_follow_up_item
from worker_queue import process_queue_jobs

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


async def prepare_tags(db, jobs):
    """Shared prepare function for analysis and follow_up workers."""
    user_emails = {job.get('user_email') for job in jobs if job.get('user_email')}
    tags_by_user = {}
    for email in user_emails:
        tags_by_user[email] = await db.get_user_tags(email)
    return {"tags_by_user": tags_by_user}


JOB_TYPE_CONFIG = {
    "analysis": {
        "process_fn": _process_analysis_item,
        "prepare_fn": prepare_tags,
        "halt_on_error": False,
    },
    "normalize": {
        "process_fn": partial(_process_normalize_item, allow_missing_analysis=False),
        "prepare_fn": None,
        "halt_on_error": True,
    },
    "follow_up": {
        "process_fn": _process_follow_up_item,
        "prepare_fn": prepare_tags,
        "halt_on_error": False,
    },
}


def main():
    parser = argparse.ArgumentParser(description="Consolidated worker for Cloud Run Jobs.")
    parser.add_argument("--job-type", required=True, choices=list(JOB_TYPE_CONFIG.keys()),
                        help="Type of jobs to process")
    parser.add_argument("--limit", type=int, default=20, help="Max jobs to lease per batch (default: 20)")
    parser.add_argument("--lease-seconds", type=int, default=600, help="Lease duration in seconds (default: 600)")

    args = parser.parse_args()

    config = JOB_TYPE_CONFIG[args.job_type]

    logger.info(f"Starting consolidated worker for job_type={args.job_type}, limit={args.limit}")

    asyncio.run(process_queue_jobs(
        job_type=args.job_type,
        limit=args.limit,
        lease_seconds=args.lease_seconds,
        get_db=get_db,
        process_item_fn=config["process_fn"],
        logger=logger,
        halt_on_error=config["halt_on_error"],
        prepare_fn=config["prepare_fn"],
        continuous=False,  # Batch mode: process available jobs, then exit
    ))


if __name__ == "__main__":
    main()
