import sys
import os
import asyncio
import argparse
from dotenv import load_dotenv

# Add backend directory to path so we can import database
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from database import FirestoreDatabase, SQLiteDatabase
from worker_manager import get_db

async def retry_failed_jobs(job_type=None, job_id=None, stale_leased=False):
    print("Initializing Database connection...")
    db = await get_db()

    if job_id:
        print(f"Retrying single job: {job_id}")
        success = await db.reset_worker_job(job_id)
        if success:
            print("Successfully reset job.")
        else:
            print(f"Failed to reset job {job_id} or job not found.")
        return

    if stale_leased:
        print(f"--- Searching for expired leased jobs {f'of type {job_type}' if job_type else ''} ---")
        jobs = await db.get_expired_leased_worker_jobs(job_type=job_type)
    else:
        print(f"--- Searching for failed jobs {f'of type {job_type}' if job_type else ''} ---")
        jobs = await db.get_failed_worker_jobs(job_type=job_type)

    print(f"Found {len(jobs)} {'expired leased' if stale_leased else 'failed'} jobs.")

    reset_count = 0
    for job in jobs:
        j_id = job.get('firestore_id') or job.get('id')
        j_type = job.get('job_type')
        print(f"Resetting {'expired leased' if stale_leased else 'failed'} {j_type} job {j_id}")

        success = await db.reset_worker_job(j_id)
        if success:
            reset_count += 1

    print(f"\nSuccessfully reset {reset_count} jobs.")
    return

def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Retry failed worker jobs.")
    parser.add_argument("--job-type", type=str, help="Retry all failed jobs of this type (e.g. podcast_audio, normalize, analysis)")
    parser.add_argument("--job-id", type=str, help="Retry a specific job by ID")
    parser.add_argument("--stale-leased", action="store_true", help="Retry all jobs with expired leases instead of failed jobs")
    
    args = parser.parse_args()
    
    asyncio.run(retry_failed_jobs(job_type=args.job_type, job_id=args.job_id, stale_leased=args.stale_leased))

if __name__ == "__main__":
    main()
