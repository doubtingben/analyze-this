import os
import socket
from uuid import uuid4
import asyncio

from tracing import (
    init_tracing, shutdown_tracing, extract_trace_context,
    create_linked_span, create_span, add_span_attributes,
    record_exception, add_span_event
)


async def start_health_check_server():
    """Starts a simple HTTP server for Cloud Run health checks."""
    port = int(os.getenv("PORT", 8080))
    
    async def handle_client(reader, writer):
        data = await reader.read(100)
        # We don't really care about the request data, just respond OK
        response = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\n\r\nOK"
        writer.write(response.encode('utf-8'))
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle_client, '0.0.0.0', port)
    print(f"Health check server listening on port {port}")
    async with server:
        await server.serve_forever()


async def process_queue_jobs(
    job_type,
    limit,
    lease_seconds,
    get_db,
    process_item_fn,
    logger,
    halt_on_error=False,
    prepare_fn=None,
    continuous=False,
    sleep_interval=10,
):
    # Initialize tracing for the worker
    init_tracing()

    db = await get_db()

    # Generate a stable worker ID for this session
    worker_id = os.getenv("WORKER_ID") or f"{socket.gethostname()}-{os.getpid()}-{uuid4().hex[:6]}"
    logger.info(f"Worker {worker_id} started for {job_type} jobs. Continuous: {continuous}")

    if continuous:
        # Start health check server in background
        asyncio.create_task(start_health_check_server())

    try:
        while True:
            jobs = await db.lease_worker_jobs(job_type, worker_id=worker_id, limit=limit, lease_seconds=lease_seconds)

            if not jobs:
                if not continuous:
                    logger.info(f"No queued {job_type} jobs found. Exiting.")
                    return

                # If continuous, sleep and try again
                logger.debug(f"No jobs found, sleeping for {sleep_interval}s...")
                await asyncio.sleep(sleep_interval)
                continue

            logger.info(f"Leased {len(jobs)} {job_type} jobs.")

            context = {}
            if prepare_fn:
                context = await prepare_fn(db, jobs)

            for job in jobs:
                job_id = job.get('firestore_id') or job.get('id')
                item_id = job.get('item_id')
                job_payload = job.get('payload', {})

                # Extract trace context from job payload for distributed tracing
                parent_ctx = extract_trace_context(job_payload)

                # Create a linked span that references the original API request trace
                with create_linked_span(
                    f"worker.{job_type}",
                    link_context=parent_ctx,
                    attributes={
                        "job.id": job_id or "unknown",
                        "job.type": job_type,
                        "job.item_id": item_id or "unknown",
                        "worker.id": worker_id,
                    }
                ) as job_span:
                    if not item_id:
                        logger.error(f"Job {job_id} missing item_id.")
                        job_span.set_attribute("job.error", "missing_item_id")
                        if job_id:
                            await db.fail_worker_job(job_id, "missing_item_id")
                        continue

                    # Fetch item data
                    with create_span("fetch_item", {"item.id": item_id}) as fetch_span:
                        data = await db.get_shared_item(item_id)
                        if not data:
                            logger.error(f"Item {item_id} not found for job {job_id}.")
                            fetch_span.set_attribute("item.found", False)
                            job_span.set_attribute("job.error", "item_not_found")
                            if job_id:
                                await db.fail_worker_job(job_id, "item_not_found")
                            continue
                        fetch_span.set_attribute("item.found", True)
                        fetch_span.set_attribute("item.type", data.get('type', 'unknown'))

                    doc_id = data.get('firestore_id') or item_id
                    job_span.set_attribute("item.doc_id", doc_id)
                    logger.info(f"Processing queued {job_type} job {job_id} for item {doc_id}...")

                    try:
                        with create_span("process_item") as process_span:
                            success, error = await process_item_fn(db, data, context)
                            process_span.set_attribute("process.success", success)
                            if error:
                                process_span.set_attribute("process.error", error)

                        if success:
                            job_span.set_attribute("job.status", "completed")
                            add_span_event("job_completed", {"job_id": job_id})
                            if job_id:
                                await db.complete_worker_job(job_id)
                        else:
                            job_span.set_attribute("job.status", "failed")
                            job_span.set_attribute("job.error", error or "job_failed")
                            if job_id:
                                await db.fail_worker_job(job_id, error or "job_failed")
                            if halt_on_error:
                                raise RuntimeError(error or "job_failed")
                    except Exception as exc:
                        logger.error(f"Job {job_id} failed with exception: {exc}")
                        job_span.set_attribute("job.status", "exception")
                        record_exception(exc)
                        if job_id:
                            await db.fail_worker_job(job_id, str(exc))
                        if halt_on_error:
                            raise

            # If not continuous, loop will finish naturally after one batch?
            # Actually logic above returns if no jobs.
            # If we processed jobs, we should loop again to check for more, OR return if !continuous.
            # But standard batch behavior usually exits after one empty check or one batch?
            # Let's say: !continuous -> run once (one lease attempt).
            # We already handled !jobs return.
            # So if we processed jobs, we check !continuous to break.
            if not continuous:
                logger.info("Batch complete. Exiting.")
                break
    finally:
        # Shutdown tracing to flush any pending spans
        shutdown_tracing()
