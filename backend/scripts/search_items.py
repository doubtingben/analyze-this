
import asyncio
import sys
import os
import argparse

# Add parent directory to path to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import FirestoreDatabase, SQLiteDatabase
from analysis import generate_embedding
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def search_items(query, user_email, limit=10):
    # Determine DB
    if os.getenv("APP_ENV") == "development":
        db = SQLiteDatabase()
        await db.init_db()
    else:
        db = FirestoreDatabase()

    logger.info(f"Using database: {type(db).__name__}")

    # Generate embedding for query
    logger.info(f"Generating embedding for query: '{query}'")
    query_embedding = generate_embedding(query)

    if not query_embedding:
        logger.error("Failed to generate embedding for query.")
        return

    logger.info(f"Searching for similar items for user {user_email}...")
    results = await db.search_similar_items(query_embedding, user_email, limit=limit)

    if results:
        logger.info(f"Found {len(results)} items:")
        for res in results:
            analysis = res.get('analysis') or {}
            overview = analysis.get('overview', 'No overview')
            logger.info(f"Item ID: {res.get('firestore_id')}")
            logger.info(f"Title: {res.get('title')}")
            logger.info(f"Overview: {overview}")
            logger.info("-" * 20)
    else:
        logger.info("No items found.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("query", type=str, help="Search query")
    parser.add_argument("email", type=str, help="User email to search for")
    parser.add_argument("--limit", type=int, default=10, help="Number of results to return")
    args = parser.parse_args()

    asyncio.run(search_items(args.query, args.email, limit=args.limit))
