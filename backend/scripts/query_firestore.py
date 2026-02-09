import sys
import os
from dotenv import load_dotenv

# Add backend directory to path so we can import database
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from database import FirestoreDatabase
from google.cloud.firestore import FieldFilter

# Load environment variables
load_dotenv()

def query_firestore():
    print("Initializing Firestore connection...")
    try:
        # Initialize the database wrapper (handles auth)
        db_wrapper = FirestoreDatabase()
        db = db_wrapper.db # This is the raw google.cloud.firestore.Client
    except Exception as e:
        print(f"Error connecting to Firestore: {e}")
        print("Make sure you have valid credentials (e.g. GOOGLE_APPLICATION_CREDENTIALS set or gcloud auth application-default login)")
        return

    collection_ref = db.collection('shared_items')

    print("\n--- Items where is_normalized == False ---")
    
    # Query for items where is_normalized is explicitly False
    query = collection_ref.where(filter=FieldFilter('is_normalized', '==', False))
    results = list(query.stream())
    
    print(f"Found {len(results)} unnormalized items.")
    
    unnormalized_ids = []
    
    for i, doc in enumerate(results):
        unnormalized_ids.append(doc.id)
        data = doc.to_dict()
        print(f"\n[{i+1}/{len(results)}] Item ID: {doc.id}")
        print("Fields:")
        # Sort keys for easier reading
        for key in sorted(data.keys()):
            value = data[key]
            print(f"  {key}: {value}")
        print("-" * 50)

    if unnormalized_ids:
        print("\n\n--- Worker Queue Jobs for these Items ---")
        worker_queue_ref = db.collection('worker_queue')
        
        for item_id in unnormalized_ids:
            print(f"\nChecking Queue for Item ID: {item_id}")
            # Query for jobs related to this item_id
            queue_query = worker_queue_ref.where(filter=FieldFilter('item_id', '==', item_id))
            queue_docs = list(queue_query.stream())
            
            if not queue_docs:
                print("  No worker jobs found.")
            else:
                for q_doc in queue_docs:
                    q_data = q_doc.to_dict()
                    print(f"  [Job ID: {q_doc.id}]")
                    for key in sorted(q_data.keys()):
                        print(f"    {key}: {q_data[key]}")
                    print("  " + "-" * 20)

if __name__ == "__main__":
    query_firestore()
