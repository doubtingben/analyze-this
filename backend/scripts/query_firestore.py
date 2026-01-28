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
        # We use the existing class to ensure consistent initialization
        db_wrapper = FirestoreDatabase()
        db = db_wrapper.db # This is the raw google.cloud.firestore.Client
    except Exception as e:
        print(f"Error connecting to Firestore: {e}")
        print("Make sure you have valid credentials (e.g. GOOGLE_APPLICATION_CREDENTIALS set or gcloud auth application-default login)")
        return

    collection_ref = db.collection('shared_items')

    # Example 1: Query for analysis == None
    print("\n--- 1. Items where analysis is null (None) ---")
    # This checks if the field is explicitly set to null
    # Using FieldFilter to avoid UserWarning about positional arguments
    query1 = collection_ref.where(filter=FieldFilter('analysis', '==', None))
    results1 = list(query1.stream())
    print(f"Found {len(results1)} items.")
    for doc in results1[:5]: # Show first 5
        data = doc.to_dict()
        print(f" - {doc.id} | Title: {data.get('title', 'No Title')} | Status: {data.get('status')}")

    # Example 2: Query for analysis.follow_up == True
    # Note: querying nested fields uses dot notation.
    # This works if 'analysis' is a map and has a boolean key 'follow_up'.
    print("\n--- 2. Items where analysis.follow_up is True ---")
    query2 = collection_ref.where(filter=FieldFilter('analysis.follow_up', '==', True))
    results2 = list(query2.stream())
    print(f"Found {len(results2)} items.")
    for doc in results2[:5]:
        data = doc.to_dict()
        analysis = data.get('analysis', {})
        # Handle case where analysis might be None in python dict even if query matched (unlikely but safe)
        if analysis:
            follow_up = analysis.get('follow_up')
        else:
            follow_up = "N/A"
        print(f" - {doc.id} | Follow Up: {follow_up}")
        
    # Example 3: Query for analysis.action == 'follow_up' (Alternative interpretation)
    print("\n--- 3. Items where analysis.action is 'follow_up' ---")
    query3 = collection_ref.where(filter=FieldFilter('analysis.action', '==', 'follow_up'))
    results3 = list(query3.stream())
    print(f"Found {len(results3)} items.")
    for doc in results3[:5]:
        data = doc.to_dict()
        print(f" - {doc.id} | Action: {data.get('analysis', {}).get('action')}")

    # Example 4: Query for status == 'follow_up'
    print("\n--- 4. Items where status is 'follow_up' ---")
    query4 = collection_ref.where(filter=FieldFilter('status', '==', 'follow_up'))
    results4 = list(query4.stream())
    print(f"Found {len(results4)} items.")
    for doc in results4[:5]:
        data = doc.to_dict()
        print(f" - {doc.id} | Status: {data.get('status')}")

if __name__ == "__main__":
    query_firestore()
