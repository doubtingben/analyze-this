import sys
import os
import argparse
import asyncio
from dotenv import load_dotenv

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from database import SQLiteDatabase, FirestoreDatabase, DBSharedItem
from sqlalchemy import text
from sqlalchemy.future import select

# Load environment variables
load_dotenv()

async def clear_item(db, item_id, reset_status=False):
    updates = {'analysis': None, 'next_step': None}
    if reset_status:
        updates['status'] = 'new'
    
    print(f"Clearing analysis for item {item_id}...")
    try:
        if isinstance(db, FirestoreDatabase):
            # Firestore implementation
            ref = db.db.collection('shared_items').document(item_id)
            doc = ref.get()
            if not doc.exists:
                print(f"Item {item_id} not found.")
                return False
            ref.update(updates)
        elif isinstance(db, SQLiteDatabase):
            # SQLite implementation
            # We can use update_shared_item but it might check for existence first which is fine.
            # However, update_shared_item in SQLiteDatabase implementation (as I recall) 
            # might technically just work if we use it, but let's check it.
            # Looking at database.py, update_shared_item takes (item_id, updates).
            success = await db.update_shared_item(item_id, updates)
            if not success:
               print(f"Item {item_id} not found.")
               return False
        
        print(f"Successfully cleared item {item_id}")
        return True
    except Exception as e:
        print(f"Error clearing item {item_id}: {e}")
        return False

async def clear_all_items(db, reset_status=False):
    updates = {'analysis': None, 'next_step': None}
    if reset_status:
        updates['status'] = 'new'

    print("Clearing analysis for ALL items...")
    count = 0
    
    if isinstance(db, FirestoreDatabase):
        # Firestore implementation
        # Note: This might be slow for huge collections, but fine for now.
        docs = db.db.collection('shared_items').stream()
        for doc in docs:
            # We can do batch writes if needed, but for script simplicity we'll do one by one or batched manually
            # For massive datasets, we should use batch.
            doc.reference.update(updates)
            print(f"Cleared {doc.id}")
            count += 1
            
    elif isinstance(db, SQLiteDatabase):
        # SQLite implementation
        async with db.SessionLocal() as session:
            # We can do a bulk update
            # update(DBSharedItem).values(analysis=None)
            from sqlalchemy import update
            stmt = update(DBSharedItem).values(**updates)
            result = await session.execute(stmt)
            await session.commit()
            count = result.rowcount
            
    print(f"Successfully cleared {count} items.")

async def main():
    parser = argparse.ArgumentParser(description="Clear analysis for shared items.")
    parser.add_argument('--id', help="The ID of the item to clear.")
    parser.add_argument('--all', action='store_true', help="Clear ALL items.")
    parser.add_argument('--env', help="Environment to use (development/production). Defaults to APP_ENV or development.")
    parser.add_argument('--reset-status', action='store_true', help="Also reset status to 'new'.")
    
    args = parser.parse_args()
    
    if not args.id and not args.all:
        parser.error("You must provide either --id or --all")
        
    if args.id and args.all:
         parser.error("You cannot provide both --id and --all")

    app_env = args.env or os.getenv("APP_ENV", "development")
    print(f"Running in {app_env} environment")
    
    db = None
    if app_env == "development":
        db = SQLiteDatabase()
        # Initialize DB if needed (usually handled by app but good to ensure)
        await db.init_db() 
    else:
        db = FirestoreDatabase()
        
    try:
        if args.id:
            await clear_item(db, args.id, args.reset_status)
        elif args.all:
            confirmation = input("Are you SURE you want to clear analysis for ALL items? (y/N): ")
            if confirmation.lower() == 'y':
                await clear_all_items(db, args.reset_status)
            else:
                print("Operation cancelled.")
    finally:
        # Cleanup if necessary
        pass

if __name__ == "__main__":
    asyncio.run(main())
