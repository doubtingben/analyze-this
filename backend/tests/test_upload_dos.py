import unittest
from unittest.mock import MagicMock, patch, ANY
import os
import sys
import importlib
from fastapi.testclient import TestClient

# Add backend directory to path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

class TestUploadDoS(unittest.TestCase):
    def setUp(self):
        # 1. Patch Environment
        self.env_patcher = patch.dict(os.environ, {
            "APP_ENV": "production",
            "SECRET_KEY": "a-very-secure-secret-key-for-testing",
            "GOOGLE_CLIENT_ID": "mock",
            "GOOGLE_CLIENT_SECRET": "mock"
        })
        self.env_patcher.start()

        # 2. Patch sys.modules for firebase
        self.firebase_mock = MagicMock()
        self.storage_mock = MagicMock()
        self.firebase_mock.storage = self.storage_mock

        self.modules_patcher = patch.dict(sys.modules, {
            "firebase_admin": self.firebase_mock,
            "firebase_admin.credentials": MagicMock(),
            "firebase_admin.storage": self.storage_mock,
            "firebase_admin.firestore": MagicMock(),
        })
        self.modules_patcher.start()

        # 3. Reload main to pick up env and mocks
        import main
        importlib.reload(main)
        self.app = main.app
        self.client = TestClient(self.app)

        # 4. Patch verify_google_token
        self.verify_patcher = patch("main.verify_google_token")
        self.mock_verify = self.verify_patcher.start()
        self.mock_verify.return_value = {"email": "test@example.com"}

        # Configure storage mock
        self.mock_bucket = MagicMock()
        self.mock_blob = MagicMock()
        self.storage_mock.bucket.return_value = self.mock_bucket
        self.mock_bucket.blob.return_value = self.mock_blob

        # Mock FirestoreDatabase in main
        self.db_patcher = patch("main.FirestoreDatabase")
        self.mock_db_class = self.db_patcher.start()
        self.mock_db_instance = self.mock_db_class.return_value
        async def mock_create(item):
            return item
        self.mock_db_instance.create_shared_item.side_effect = mock_create

    def tearDown(self):
        self.db_patcher.stop()
        self.verify_patcher.stop()
        self.modules_patcher.stop()
        self.env_patcher.stop()

        # Reset main module to development state so it doesn't crash on reload
        with patch.dict(os.environ, {"APP_ENV": "development"}):
            import main
            importlib.reload(main)

    def test_upload_uses_streaming(self):
        """Test that file upload uses upload_from_file (streaming) instead of upload_from_string."""
        files = {'file': ('test.png', b'fake-image', 'image/png')}
        headers = {"Authorization": "Bearer token"}

        with self.client:
            response = self.client.post("/api/share", files=files, headers=headers)

            self.assertEqual(response.status_code, 200)

            # Verify upload_from_file is called
            self.mock_blob.upload_from_file.assert_called()
            self.mock_blob.upload_from_string.assert_not_called()

    def test_title_length_limit(self):
        """Test that title length is limited."""
        long_title = "a" * 256 # Limit 255
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
