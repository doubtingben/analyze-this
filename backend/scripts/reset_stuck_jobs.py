import sys
import os
import asyncio
from dotenv import load_dotenv

# Add backend directory to path so we can import database
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from database import FirestoreDatabase, WorkerJobStatus
from google.cloud.firestore import FieldFilter

# Load environment variables
load_dotenv()

async def reset_stuck_normalization_jobs():
    print("Initializing Firestore connection...")
    try:
        # Initialize the database wrapper
        db_wrapper = FirestoreDatabase()
        db = db_wrapper.db
    except Exception as e:
        print(f"Error connecting to Firestore: {e}")
        return

    collection_ref = db.collection('shared_items')
    worker_queue_ref = db.collection('worker_queue')

    print("\n--- Searching for unnormalized items with completed worker jobs ---")
    
    # 1. Get unnormalized items
    query = collection_ref.where(filter=FieldFilter('is_normalized', '==', False))
    results = list(query.stream())
    
    print(f"Found {len(results)} unnormalized items.")
    
    reset_count = 0
    
    for doc in results:
        item_id = doc.id
        
        # 2. Find associated normalize jobs
        queue_query = worker_queue_ref.where(filter=FieldFilter('item_id', '==', item_id)).where(filter=FieldFilter('job_type', '==', 'normalize'))
        queue_docs = list(queue_query.stream())
        
        for q_doc in queue_docs:
            q_data = q_doc.to_dict()
            status = q_data.get('status')
            
            if status == 'completed':
                print(f"Resetting STUCK job {q_doc.id} for item {item_id} (Status: {status})")
                
                # 3. Reset to queued
                q_doc.reference.update({
                    'status': 'queued',
                    'attempts': 0,
                    'error': None, # Clear any error just in case
                    'worker_id': None,
                    'lease_expires_at': None,
                    'updated_at': db_wrapper.db.server_timestamp() if hasattr(db_wrapper.db, 'server_timestamp') else None
                })
                reset_count += 1
            else:
                 print(f"Skipping job {q_doc.id} for item {item_id} (Status: {status})")

    print(f"\nSuccessfully reset {reset_count} jobs.")

if __name__ == "__main__":
    asyncio.run(reset_stuck_normalization_jobs())
