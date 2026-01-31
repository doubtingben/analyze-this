import os
import socket
from uuid import uuid4


async def process_queue_jobs(
    job_type,
    limit,
    lease_seconds,
    get_db,
    process_item_fn,
    logger,
    halt_on_error=False,
):
    db = await get_db()
    worker_id = os.getenv("WORKER_ID") or f"{socket.gethostname()}-{os.getpid()}-{uuid4().hex[:6]}"

    jobs = await db.lease_worker_jobs(job_type, worker_id=worker_id, limit=limit, lease_seconds=lease_seconds)
    if not jobs:
        logger.info(f"No queued {job_type} jobs found.")
        return

    for job in jobs:
        job_id = job.get('firestore_id') or job.get('id')
        item_id = job.get('item_id')
        if not item_id:
            logger.error(f"Job {job_id} missing item_id.")
            if job_id:
                await db.fail_worker_job(job_id, "missing_item_id")
            continue

        data = await db.get_shared_item(item_id)
        if not data:
            logger.error(f"Item {item_id} not found for job {job_id}.")
            if job_id:
                await db.fail_worker_job(job_id, "item_not_found")
            continue

        doc_id = data.get('firestore_id') or item_id
        logger.info(f"Processing queued {job_type} job {job_id} for item {doc_id}...")

        try:
            success, error = await process_item_fn(db, data)
            if success:
                if job_id:
                    await db.complete_worker_job(job_id)
            else:
                if job_id:
                    await db.fail_worker_job(job_id, error or "job_failed")
                if halt_on_error:
                    raise RuntimeError(error or "job_failed")
        except Exception as exc:
            logger.error(f"Job {job_id} failed with exception: {exc}")
            if job_id:
                await db.fail_worker_job(job_id, str(exc))
            if halt_on_error:
                raise
