import unittest
from unittest.mock import MagicMock, patch, ANY
import os
import sys

# Setup environment to PRODUCTION to test GCS path
os.environ["APP_ENV"] = "production"
os.environ["SECRET_KEY"] = "secure-test-key-12345"
os.environ["GOOGLE_CLIENT_ID"] = "mock"
os.environ["GOOGLE_CLIENT_SECRET"] = "mock"

# Mock firebase_admin before importing main
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.storage"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()

# Add backend directory to path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

from main import app
import main

from fastapi.testclient import TestClient

class TestUploadDoS(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

        # Patch APP_ENV to production for these tests
        self.env_patcher = patch("main.APP_ENV", "production")
        self.env_patcher.start()

        # Patch verify_google_token
        self.verify_patcher = patch("main.verify_google_token")
        self.mock_verify = self.verify_patcher.start()
        self.mock_verify.return_value = {"email": "test@example.com"}

        # Patch storage in main
        self.storage_patcher = patch("main.storage")
        self.mock_storage = self.storage_patcher.start()
        self.mock_bucket = MagicMock()
        self.mock_blob = MagicMock()
        self.mock_storage.bucket.return_value = self.mock_bucket
        self.mock_bucket.blob.return_value = self.mock_blob

        # Mock FirestoreDatabase in main
        self.db_patcher = patch("main.FirestoreDatabase")
        self.mock_db_class = self.db_patcher.start()
        self.mock_db_instance = self.mock_db_class.return_value
        async def mock_create(item):
            return item
        self.mock_db_instance.create_shared_item.side_effect = mock_create

        # We also need to prevent lifespan from running normally or just let it use mocks
        # Since we mocked FirestoreDatabase class, it should be fine.

    def tearDown(self):
        self.env_patcher.stop()
        self.verify_patcher.stop()
        self.storage_patcher.stop()
        self.db_patcher.stop()

    def test_upload_uses_streaming(self):
        """Test that file upload uses upload_from_file (streaming) instead of upload_from_string."""
        files = {'file': ('test.png', b'fake-image', 'image/png')}
        headers = {"Authorization": "Bearer token"}

        # Use context manager to trigger lifespan
        with self.client:
            # Need to force db to be our mock if lifespan overwrites it
            # But lifespan uses FirestoreDatabase() which we mocked.
            # So main.db will be our mock instance.

            response = self.client.post("/api/share", files=files, headers=headers)

            self.assertEqual(response.status_code, 200)

            # Verify upload_from_file is called
            # Note: We need to verify that upload_from_file was called on the blob
            # AND that upload_from_string was NOT called.

            # Since existing code uses upload_from_string, this test is expected to fail initially
            # if we assert upload_from_file.
            # We will assert this to prove the fix.
            self.mock_blob.upload_from_file.assert_called()
            self.mock_blob.upload_from_string.assert_not_called()

    def test_title_length_limit(self):
        """Test that title length is limited."""
        long_title = "a" * 256 # Limit 255
        # We must use files to trigger multipart/form-data which the endpoint expects
        # We can pass data as tuple in files to be part of multipart
        # Or just pass files={} to force multipart, but TestClient/requests is tricky.
        # Simplest is to treat fields as files with None filename? No.
        # Requests handles data+files as multipart.

        # We need to force content-type to contain multipart/form-data
        # But requests generates the boundary.
        # If we pass a dummy file, it switches to multipart.
        files = {'dummy': ('dummy.txt', b'')}
        data = {"title": long_title, "type": "text", "content": "short"}
        headers = {"Authorization": "Bearer token"}

        with self.client:
            response = self.client.post("/api/share", data=data, files=files, headers=headers)
            self.assertEqual(response.status_code, 400)
            self.assertIn("Title too long", response.text)

    def test_content_length_limit(self):
        """Test that content length is limited."""
        long_content = "a" * 10001 # Limit 10000
        files = {'dummy': ('dummy.txt', b'')}
        data = {"title": "ok", "type": "text", "content": long_content}
        headers = {"Authorization": "Bearer token"}

        with self.client:
            response = self.client.post("/api/share", data=data, files=files, headers=headers)
            self.assertEqual(response.status_code, 400)
            self.assertIn("Content too long", response.text)

if __name__ == "__main__":
    unittest.main()
