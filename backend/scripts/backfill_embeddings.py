
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

async def backfill_embeddings(force=False):
    # Determine DB
    if os.getenv("APP_ENV") == "development":
        db = SQLiteDatabase()
        await db.init_db()
    else:
        db = FirestoreDatabase()

    logger.info(f"Using database: {type(db).__name__}")

    # Fetch all items (or implement pagination if many items)
    # For now, fetching recent 500 items should be enough for a demo or start
    # Ideally, we should iterate all items.
    
    # Firestore get_shared_items gets all items for a user.
    # We want ALL shared items across users if we are admin, but here we run as a script.
    # We can iterate collections directly if using Firestore SDK, but let's stick to DB interface if possible.
    # DB interface doesn't have "get_all_items".
    
    if isinstance(db, FirestoreDatabase):
        items_ref = db.db.collection('shared_items')
        docs = items_ref.stream()
        
        count = 0
        updated = 0
        
        for doc in docs:
            count += 1
            data = doc.to_dict()
            item_id = doc.id
            
            if not force and data.get('embedding'):
                continue
                
            analysis = data.get('analysis')
            if not analysis:
                logger.warning(f"Item {item_id} has no analysis. Skipping.")
                continue
                
            overview = analysis.get('overview') or analysis.get('summary')
            if not overview:
                logger.warning(f"Item {item_id} has no overview. Skipping.")
                continue
                
            logger.info(f"Generating embedding for item {item_id}...")
            embedding = generate_embedding(overview)
            
            if embedding:
                # Update document
                db.db.collection('shared_items').document(item_id).update({'embedding': embedding})
                updated += 1
                logger.info(f"Updated item {item_id}")
            else:
                logger.error(f"Failed to generate embedding for {item_id}")
                
        logger.info(f"Processed {count} items. Updated {updated} embeddings.")
        
    else:
        logger.warning("Backfill only implemented for Firestore in this script for now.")
        
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Force regenerate embeddings")
    args = parser.parse_args()
    
    asyncio.run(backfill_embeddings(force=args.force))
