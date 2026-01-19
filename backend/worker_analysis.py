import os
import argparse
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import Client as FirestoreClient
from dotenv import load_dotenv
import logging
from analysis import analyze_content

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def initialize_firebase():
    """Initializes Firebase if not already initialized."""
    if not firebase_admin._apps:
        try:
            # Check if running in Cloud Run or locally with credentials
            firebase_admin.initialize_app(options={
                'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET')
            })
            logger.info("Firebase initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            raise e

def process_items(limit: int = 10, item_id: str = None, force: bool = False):
    """
    Processes unanalyzed items from Firestore.
    
    Args:
        limit: Maximum number of items to process in this run.
        item_id: Specific item ID to process (overrides limit/unanalyzed check if force is True).
        force: If True, re-analyze even if analysis exists (only valid with item_id).
    """
    db: FirestoreClient = firestore.client()
    items_ref = db.collection('shared_items')
    
    docs_to_process = []

    if item_id:
        # Fetch specific document
        logger.info(f"Fetching specific item with ID: {item_id}")
        doc_ref = items_ref.document(item_id)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            # If force is True OR analysis is missing, process it
            if force or not data.get('analysis'):
                 docs_to_process.append((doc.id, data))
            else:
                logger.info(f"Item {item_id} already has analysis. Use --force to re-analyze.")
        else:
            logger.error(f"Item {item_id} not found.")
    else:
        # Query for items without analysis
        # Note: 'analysis' field might not exist, or be null.
        # Queries for missing fields are tricky in Firestore (no direct "is missing" filter in all SDKs easily).
        # We can look for where analysis == None explicitly if stored as null,
        # or we might have to rely on application logic if the field is just missing.
        # Alternatively, we can add a 'status' field.
        # For now, let's try querying where analysis == None.
        logger.info(f"Querying for up to {limit} unanalyzed items...")
        
        # Firestore query strict equality for null
        query = items_ref.where(field_path='analysis', op_string='==', value=None).limit(limit)
        results = list(query.stream())
        
        # If the field is completely missing (not null), the above might not catch it depending on existing data.
        # Let's also check if we can query strictly by "analysis" field absence? No direct "exists" query.
        # But if we saved them with default=None in Pydantic, they should be null in DB if serialized correctly.
        
        for doc in results:
            docs_to_process.append((doc.id, doc.to_dict()))
            
        logger.info(f"Found {len(docs_to_process)} items to process.")

    for doc_id, data in docs_to_process:
        logger.info(f"Analyzing item {doc_id} ({data.get('type')})...")
        
        content = data.get('content')
        item_type = data.get('type', 'text')
        
        if not content:
            logger.warning(f"Item {doc_id} has no content. Skipping.")
            continue
            
        try:
            analysis_result = analyze_content(content, item_type)
            
            if analysis_result:
                # Update Firestore
                items_ref.document(doc_id).update({
                    'analysis': analysis_result
                })
                logger.info(f"Successfully updated item {doc_id} with analysis.")
            else:
                logger.warning(f"Analysis returned None for item {doc_id}.")
                
        except Exception as e:
            logger.error(f"Failed to analyze item {doc_id}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Worker to process unanalyzed shared items.")
    parser.add_argument("--limit", type=int, default=10, help="Number of items to process (default: 10)")
    parser.add_argument("--id", type=str, help="Specific Item ID to process")
    parser.add_argument("--force", action="store_true", help="Force re-analysis if ID is provided")
    
    args = parser.parse_args()
    
    initialize_firebase()
    process_items(limit=args.limit, item_id=args.id, force=args.force)
