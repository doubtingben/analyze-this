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

class TestDownloadDoS(unittest.TestCase):
    def setUp(self):
        # 1. Patch Environment to Production
        self.env_patcher = patch.dict(os.environ, {
            "APP_ENV": "production",
            "SECRET_KEY": "secure-key-for-testing",
            "GOOGLE_CLIENT_ID": "mock",
            "GOOGLE_CLIENT_SECRET": "mock"
        })
        self.env_patcher.start()

        # 2. Mock firebase_admin modules in sys.modules
        self.firebase_mock = MagicMock()
        self.storage_mock = MagicMock()

        # Ensure consistency between module lookup and attribute lookup
        self.firebase_mock.storage = self.storage_mock

        self.sys_modules_patcher = patch.dict(sys.modules, {
            "firebase_admin": self.firebase_mock,
            "firebase_admin.credentials": MagicMock(),
            "firebase_admin.storage": self.storage_mock,
            "firebase_admin.firestore": MagicMock(),
        })
        self.sys_modules_patcher.start()

        # 3. Reload main to pick up the new env and mocks
        import main
        importlib.reload(main)
        self.app = main.app
        self.client = TestClient(self.app)

        # 4. Patch internal main dependencies (verify_google_token, etc)
        self.verify_patcher = patch("main.verify_google_token")
        self.mock_verify = self.verify_patcher.start()
        self.mock_verify.return_value = {"email": "test@example.com"}

        # Configure storage
        self.mock_bucket = MagicMock()
        self.mock_blob = MagicMock()
        self.storage_mock.bucket.return_value = self.mock_bucket
        self.mock_bucket.blob.return_value = self.mock_blob

        self.mock_blob.content_type = "image/png"
        self.mock_blob.download_as_bytes.return_value = b"fake-content"

        # Mock FirestoreDatabase in main
        self.db_patcher = patch("main.FirestoreDatabase")
        self.mock_db_class = self.db_patcher.start()

    def tearDown(self):
        self.verify_patcher.stop()
        self.db_patcher.stop()
        self.sys_modules_patcher.stop()
        self.env_patcher.stop()

        # Reset main module to development state
        with patch.dict(os.environ, {"APP_ENV": "development"}):
            import main
            importlib.reload(main)

    def test_download_uses_streaming(self):
        """Test that file download uses streaming (blob.open) instead of download_as_bytes."""

        headers = {"Authorization": "Bearer token"}
        file_path = "uploads/test@example.com/image.png"

        # Use a fake file class to avoid MagicMock issues
        class FakeFile:
            def __init__(self):
                self.chunks = [b"chunk1", b"chunk2"]
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self, size=None):
                if self.chunks:
                    return self.chunks.pop(0)
                return b""

        fake_file = FakeFile()
        # Ensure blob.open return value is our fake file
        self.mock_blob.open.return_value = fake_file
        # Also handle side_effect if it's being treated as a callable in a way that prefers it?
        # No, return_value should be enough if it's a mock.
        # But if it was replaced by a lambda before, we are resetting it here implicitly (new test run) or explicitly if needed.
        # MagicMock calls use return_value by default.

        with self.client:
            response = self.client.get(f"/api/content/{file_path}", headers=headers)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, b"chunk1chunk2")

            # Check that download_as_bytes is NOT called
            self.mock_blob.download_as_bytes.assert_not_called()

            # Check that blob.open is called
            self.mock_blob.open.assert_called_with("rb")

            # Check that reload was called
            self.mock_blob.reload.assert_called()

if __name__ == "__main__":
    unittest.main()
