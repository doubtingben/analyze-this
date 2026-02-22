import os
import asyncio
import logging
from dotenv import load_dotenv

from database import DatabaseInterface, FirestoreDatabase, SQLiteDatabase
from models import SharedItem
from models import TimelineEvent # Need this for parsing correctly if we were strictly using pydantic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_db() -> DatabaseInterface:
    load_dotenv()
    APP_ENV = os.getenv("APP_ENV", "production")
    if APP_ENV == "development":
        logger.info("Using SQLiteDatabase")
        db = SQLiteDatabase()
        if hasattr(db, 'init_db'):
            await db.init_db()
        return db
    else:
        logger.info("Using FirestoreDatabase")
        return FirestoreDatabase()

async def migrate_timelines():
    db = await get_db()
    # Easiest way to migrate is just to pull all items.
    
    logger.info("Fetching all items for all users...")
    
    # SQLite has get_all_items (if implemented) or we can query users and then items.
    # To be safe, we'll try to find users first or iterate if there is a method.
    
    items = []
    
    if hasattr(db, 'get_shared_items'):
        # Usually get_shared_items takes user_email. 
        # In Firestore we might need a custom query to get ALL items without filtering by user if we are migrating.
        pass
    
    if isinstance(db, SQLiteDatabase):
        from sqlalchemy import text
        logger.info("Running raw query on SQLite...")
        async with db.SessionLocal() as session:
            rows = await session.execute(text("SELECT id, user_email FROM shared_items"))
            user_emails = list(set([row[1] for row in rows]))
            for email in user_emails:
                 user_items = await db.get_shared_items(email, limit=10000)
                 items.extend(user_items)
             
    elif isinstance(db, FirestoreDatabase):
        logger.info("Querying Firestore...")
        # Since we might not want to list all users, we can just query the collection.
        # This requires importing internal firestore client.
        try:
             docs = db.db.collection('shared_items').stream()
             for doc in docs:
                 items.append(doc.to_dict())
        except Exception as e:
             logger.error(f"Error querying firestore: {e}")
             return

    logger.info(f"Found {len(items)} items to check.")
    
    migrated_count = 0
    
    for item_data in items:
        item_id = item_data.get('firestore_id') or item_data.get('id')
        if not item_id:
            continue
            
        analysis = item_data.get('analysis')
        needs_update = False
        update_payload = {}
        
        # We need to grab analysis timeline and verify if it's a dict.
        if analysis and 'timeline' in analysis:
            old_timeline = analysis['timeline']
            
            # If it's a list, it might already be migrated or empty.
            if isinstance(old_timeline, dict):
                logger.info(f"Migrating item: {item_id}")
                needs_update = True
                
                # Move to root timeline as a list
                root_timeline = item_data.get('timeline', [])
                if not root_timeline:
                    root_timeline = [old_timeline]
                else: 
                     # Only insert if not already present
                     root_timeline.append(old_timeline)
                     
                update_payload['timeline'] = root_timeline
                
                # Remove from analysis
                del analysis['timeline']
                update_payload['analysis'] = analysis
                
        if needs_update:
            try:
                await db.update_shared_item(item_id, update_payload)
                migrated_count += 1
            except Exception as e:
                logger.error(f"Failed to update item {item_id}: {e}")
                
    logger.info(f"Migration completed. Updated {migrated_count} items.")

if __name__ == "__main__":
    asyncio.run(migrate_timelines())
