import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from database import FirestoreDatabase, SQLiteDatabase  # noqa: E402


load_dotenv()


async def get_db(app_env: str):
    if app_env == "development":
        db = SQLiteDatabase()
        await db.init_db()
        return db
    return FirestoreDatabase()


async def requeue_podcast_audio(db, item_id: str, user_email: str, reset_status: bool) -> str:
    feed_entry = await db.get_podcast_feed_entry_by_item(user_email, item_id)
    if not feed_entry:
        raise RuntimeError(f"podcast_feed_entry_not_found:{item_id}")

    feed_entry_id = feed_entry.get("firestore_id") or feed_entry.get("id")
    if not feed_entry_id:
        raise RuntimeError(f"podcast_feed_entry_missing_id:{item_id}")

    updates = {
        "updated_at": datetime.now(timezone.utc),
        "error": None,
        "debug_source_retrieval_error": None,
        "debug_source_retrieval_details": None,
    }
    if reset_status:
        updates["status"] = "queued"

    updated = await db.update_podcast_feed_entry(feed_entry_id, updates)
    if not updated:
        raise RuntimeError(f"podcast_feed_entry_update_failed:{feed_entry_id}")

    job_id = await db.enqueue_worker_job(
        item_id,
        user_email,
        "podcast_audio",
        {"source": "manual_retry", "feed_entry_id": feed_entry_id},
    )
    return job_id


async def main() -> None:
    parser = argparse.ArgumentParser(description="Requeue a podcast audio job for a specific item.")
    parser.add_argument("--item-id", required=True, help="Shared item ID to retry.")
    parser.add_argument("--user-email", required=True, help="Owner email for the shared item.")
    parser.add_argument(
        "--env",
        default=os.getenv("APP_ENV", "development"),
        help="Environment to use (development or production). Defaults to APP_ENV.",
    )
    parser.add_argument(
        "--no-reset-status",
        action="store_true",
        help="Leave the podcast feed entry status unchanged and only enqueue a fresh worker job.",
    )
    args = parser.parse_args()

    db = await get_db(args.env)
    job_id = await requeue_podcast_audio(
        db,
        item_id=args.item_id,
        user_email=args.user_email,
        reset_status=not args.no_reset_status,
    )
    print(f"Enqueued podcast_audio job {job_id} for item {args.item_id}")


if __name__ == "__main__":
    asyncio.run(main())
