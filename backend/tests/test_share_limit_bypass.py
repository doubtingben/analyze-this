
import os
import sys
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

# Add backend directory to path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Setup Mock Environment
os.environ["APP_ENV"] = "development"
os.environ["SECRET_KEY"] = "test"
os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000"

# Mock firebase_admin BEFORE importing main
if "firebase_admin" not in sys.modules:
    sys.modules["firebase_admin"] = MagicMock()
    sys.modules["firebase_admin.credentials"] = MagicMock()
    sys.modules["firebase_admin.firestore"] = MagicMock()
    sys.modules["firebase_admin.storage"] = MagicMock()
    # Alias storage
    sys.modules["firebase_admin"].storage = sys.modules["firebase_admin.storage"]

from fastapi.testclient import TestClient

# Import app
try:
    from main import app, db, MAX_TITLE_LENGTH, MAX_TEXT_LENGTH
except Exception as e:
    print(f"Error importing main: {e}")
    sys.exit(1)

class TestShareLimitBypass(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.patcher = patch("main.db")
        self.mock_db = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    @patch("main.verify_google_token")
    def test_share_json_bypass(self, mock_verify):
        mock_verify.return_value = {"email": "test@example.com"}

        # Mock DB
        self.mock_db.create_shared_item = AsyncMock(return_value=True)
        self.mock_db.enqueue_worker_job = AsyncMock(return_value=True)

        # Huge title - larger than MAX_TITLE_LENGTH (255)
        long_title = "a" * (MAX_TITLE_LENGTH + 100)

        payload = {
            "title": long_title,
            "content": "some content",
            "type": "text"
        }

        response = self.client.post(
            "/api/share",
            json=payload,
            headers={"Authorization": "Bearer token"}
        )

        # If vulnerable, this will be 200 OK because checks are skipped
        # If fixed, this should be 400 Bad Request
        print(f"Share JSON Bypass Response Code: {response.status_code}")

        if response.status_code == 200:
             print("VULNERABILITY CONFIRMED: Large title accepted via JSON")
        else:
             print("VULNERABILITY NOT FOUND: Request rejected")

        self.assertEqual(response.status_code, 400, "Should reject huge title in JSON")

    @patch("main.verify_google_token")
    def test_share_json_content_bypass(self, mock_verify):
        mock_verify.return_value = {"email": "test@example.com"}

        self.mock_db.create_shared_item = AsyncMock(return_value=True)
        self.mock_db.enqueue_worker_job = AsyncMock(return_value=True)

        # Huge content - larger than MAX_TEXT_LENGTH (10000)
        long_content = "a" * (MAX_TEXT_LENGTH + 1000)

        payload = {
            "title": "Normal Title",
            "content": long_content,
            "type": "text"
        }

        response = self.client.post(
            "/api/share",
            json=payload,
            headers={"Authorization": "Bearer token"}
        )

        print(f"Share JSON Content Bypass Response Code: {response.status_code}")
        self.assertEqual(response.status_code, 400, "Should reject huge content in JSON")

if __name__ == "__main__":
    unittest.main()
