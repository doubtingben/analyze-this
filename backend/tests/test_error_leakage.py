import unittest
import os
import sys
import importlib
import asyncio
from unittest.mock import patch, MagicMock

# Add backend directory to path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

# Mock modules before importing main
# We need to mock everything that main imports which might cause side effects or require credentials
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.storage"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()
sys.modules["google.cloud"] = MagicMock()
sys.modules["google.cloud.firestore"] = MagicMock()
sys.modules["google.cloud.firestore_v1"] = MagicMock()
sys.modules["google.cloud.firestore_v1.base_query"] = MagicMock()
sys.modules["google.cloud.firestore_v1.batch"] = MagicMock()
sys.modules["google.cloud.firestore_v1.vector"] = MagicMock()
sys.modules["google.cloud.storage"] = MagicMock()
sys.modules["google.auth.transport.requests"] = MagicMock()
sys.modules["google.oauth2"] = MagicMock()
sys.modules["google.oauth2.id_token"] = MagicMock()

class TestErrorLeakage(unittest.TestCase):
    def setUp(self):
        # Change to backend directory so static files can be found
        os.chdir(BACKEND_DIR)

        # Force Production Env with a secure key
        self.env_patcher = patch.dict(os.environ, {
            "APP_ENV": "production",
            "SECRET_KEY": "secure-test-key-for-production-mock",
            "GOOGLE_CLIENT_ID": "mock-client-id"
        })
        self.env_patcher.start()

        # Reload main to ensure it picks up the env
        import main
        importlib.reload(main)
        from main import app

        self.app = app
        self.main = main

        # Mock the database
        self.mock_db = MagicMock()
        # Mock enqueue_worker_job to return a dummy job ID
        async def mock_enqueue(*args, **kwargs):
            return "job-id"
        self.mock_db.enqueue_worker_job.side_effect = mock_enqueue

        # Mock create_shared_item
        async def mock_create(item):
            return item
        self.mock_db.create_shared_item.side_effect = mock_create

        main.db = self.mock_db

        # Mock verify_google_token
        self.verify_token_patcher = patch('main.verify_google_token')
        self.mock_verify_token = self.verify_token_patcher.start()

        async def mock_verify_async(token):
             return {"email": "test@example.com"}
        self.mock_verify_token.side_effect = mock_verify_async

        # Mock storage
        self.mock_bucket = MagicMock()
        # main.storage is the mock we injected into sys.modules
        self.main.storage.bucket.return_value = self.mock_bucket
        self.mock_blob = MagicMock()
        self.mock_bucket.blob.return_value = self.mock_blob

        from fastapi.testclient import TestClient
        self.client = TestClient(self.app)

    def tearDown(self):
        self.env_patcher.stop()
        self.verify_token_patcher.stop()

    def test_upload_error_leakage(self):
        """
        Test that sensitive error details are NOT leaked in production when upload fails.
        """
        sensitive_error = "Connection failed to internal-storage-v2.private.net:8080"

        # Mock upload failure
        # The main code calls: blob.upload_from_file(...) in a run_in_executor
        # Since we mocked blob, we set the side effect on the method.
        self.mock_blob.upload_from_file.side_effect = Exception(sensitive_error)

        files = {
            'file': ('test.txt', b'content', 'text/plain')
        }
        data = {
            'type': 'file'
        }
        headers = {"Authorization": "Bearer valid-token"}

        response = self.client.post(
            "/api/share",
            headers=headers,
            data=data,
            files=files
        )

        self.assertEqual(response.status_code, 500)

        # Ensure generic error is returned
        self.assertEqual(response.json()['detail'], "File upload failed")
        self.assertNotIn(sensitive_error, response.json()['detail'])

if __name__ == '__main__':
    unittest.main()
