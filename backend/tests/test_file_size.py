import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import os
import sys

# Setup environment
os.environ["APP_ENV"] = "production"
os.environ["SECRET_KEY"] = "secure-test-key-12345"
os.environ["GOOGLE_CLIENT_ID"] = "mock"
os.environ["GOOGLE_CLIENT_SECRET"] = "mock"

# Mock dependencies
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.storage"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()

# Add backend directory to path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

from main import app
from fastapi.testclient import TestClient

class TestFileSizeLimit(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

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

        # Patch DB
        self.db_patcher = patch("main.db")
        self.mock_db = self.db_patcher.start()
        # Ensure db methods are AsyncMock
        self.mock_db.create_shared_item = AsyncMock()
        self.mock_db.create_item_note = AsyncMock()
        self.mock_db.get_shared_item = AsyncMock()
        self.mock_db.get_shared_item.return_value = {"user_email": "test@example.com", "id": "item1"}
        self.mock_db.enqueue_worker_job = AsyncMock()

    def tearDown(self):
        self.verify_patcher.stop()
        self.storage_patcher.stop()
        self.db_patcher.stop()

    def test_share_item_content_length_header(self):
        """Test that requests with large Content-Length header are rejected."""
        headers = {
            "Authorization": "Bearer token",
            "Content-Length": str(100 * 1024 * 1024) # 100 MB
        }

        # We try to send a request. TestClient might override Content-Length if we provide body.
        # But if we provide no body?
        response = self.client.post("/api/share", headers=headers)

        # 413 Payload Too Large
        self.assertEqual(response.status_code, 413)
        self.assertIn("File too large", response.text)

    def test_share_item_actual_size(self):
        """Test that files exceeding MAX_FILE_SIZE are rejected."""
        # Patch MAX_FILE_SIZE to be small
        with patch("main.MAX_FILE_SIZE", 10): # 10 bytes limit
            files = {"file": ("test.txt", b"12345678901", "text/plain")} # 11 bytes
            headers = {"Authorization": "Bearer token"}

            response = self.client.post("/api/share", files=files, headers=headers)

            self.assertEqual(response.status_code, 413)
            self.assertIn("File too large", response.text)

    def test_share_item_within_limit(self):
        """Test that files within MAX_FILE_SIZE are accepted."""
        with patch("main.MAX_FILE_SIZE", 2048): # 2KB
            files = {"file": ("test.txt", b"1234567890", "text/plain")} # 10 bytes
            headers = {"Authorization": "Bearer token"}

            response = self.client.post("/api/share", files=files, headers=headers)

            # Should be 200 OK (or whatever success code)
            # Note: response might be 400 if other validations fail (e.g. CSRF or mocking)
            # but we assert it is NOT 413
            self.assertNotEqual(response.status_code, 413)

    def test_create_note_content_length_header(self):
        """Test create note with large Content-Length header."""
        headers = {
            "Authorization": "Bearer token",
            "Content-Length": str(100 * 1024 * 1024)
        }
        response = self.client.post("/api/items/item1/notes", headers=headers)
        self.assertEqual(response.status_code, 413)

    def test_create_note_actual_size(self):
        """Test create note with file exceeding limit."""
        with patch("main.MAX_FILE_SIZE", 10):
            files = {"file": ("test.png", b"12345678901", "image/png")}
            headers = {"Authorization": "Bearer token"}

            # Need to provide either text or file. Here file.
            response = self.client.post("/api/items/item1/notes", files=files, headers=headers)

            self.assertEqual(response.status_code, 413)

if __name__ == "__main__":
    unittest.main()
