import asyncio
import time
import os
import sys
from unittest.mock import MagicMock, patch

# 1. Setup Environment
os.environ["APP_ENV"] = "production"
os.environ["SECRET_KEY"] = "test"

# Mock firebase modules BEFORE importing main
mock_firebase = MagicMock()
mock_storage = MagicMock()
sys.modules["firebase_admin"] = mock_firebase
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.storage"] = mock_storage

# 2. Import App
# We need to make sure we are in the backend directory so imports work
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

# Import main after mocks are set up
import main
from main import app

# 3. Setup Mocks
# Mock the storage blob upload to be slow and blocking
def blocking_upload(*args, **kwargs):
    time.sleep(0.5)

mock_bucket = MagicMock()
mock_blob = MagicMock()
mock_blob.upload_from_string.side_effect = blocking_upload
mock_bucket.blob.return_value = mock_blob
mock_storage.bucket.return_value = mock_bucket

# Ensure main.storage uses our mock
main.storage = mock_storage

# Mock Database
mock_db = MagicMock()
async def mock_upsert_user(user):
    pass
async def mock_create_shared_item(item):
    pass
mock_db.upsert_user = mock_upsert_user
mock_db.create_shared_item = mock_create_shared_item

# Patch FirestoreDatabase so lifespan initializes our mock db
main.FirestoreDatabase = MagicMock(return_value=mock_db)
# Explicitly set db because ASGITransport might not trigger lifespan
main.db = mock_db

# 4. Benchmark Function
import httpx

async def run_benchmark():
    # Use ASGITransport to communicate with the app directly
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:

        # Patch verify_google_token to return a valid user
        with patch("main.verify_google_token") as mock_verify:
            mock_verify.return_value = {"email": "test@example.com"}

            # Prepare file upload
            # We need to create fresh file objects/content for each request because httpx might read them

            start_time = time.time()

            # Send 5 concurrent requests
            tasks = []
            for i in range(5):
                files = {'file': ('test.txt', b'content', 'text/plain')}
                data = {'type': 'media'}
                tasks.append(client.post("/api/share", files=files, data=data, headers={"Authorization": "Bearer token"}))

            responses = await asyncio.gather(*tasks)

            end_time = time.time()
            duration = end_time - start_time

            # Check results
            for r in responses:
                if r.status_code != 200:
                    print(f"Request failed: {r.status_code} {r.text}")

            print(f"Total time for 5 requests: {duration:.4f} seconds")

            # Verify that our blocking mock was actually called
            call_count = mock_blob.upload_from_string.call_count
            print(f"Upload called {call_count} times")
            if call_count != 5:
                print("WARNING: Upload was not called 5 times!")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
