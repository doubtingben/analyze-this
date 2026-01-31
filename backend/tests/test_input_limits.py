
import os
import unittest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch, AsyncMock
import sys

# Setup Mock Environment
os.environ["APP_ENV"] = "development"
os.environ["SECRET_KEY"] = "test"
os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000"

# Mock firebase_admin BEFORE importing main
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()
sys.modules["firebase_admin.storage"] = MagicMock()

# Alias storage for "from firebase_admin import storage"
sys.modules["firebase_admin"].storage = sys.modules["firebase_admin.storage"]

# Import app
try:
    from main import app, db
except Exception as e:
    print(f"Error importing main: {e}")
    sys.exit(1)

class TestInputLimits(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        # Mock DB methods
        self.patcher = patch("main.db")
        self.mock_db = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    @patch("main.verify_google_token")
    def test_update_item_title_limit(self, mock_verify):
        mock_verify.return_value = {"email": "test@example.com"}

        # Mock DB Item
        self.mock_db.get_shared_item = AsyncMock(return_value={"user_email": "test@example.com", "id": "item1"})
        self.mock_db.update_shared_item = AsyncMock(return_value=True)

        # Huge title
        long_title = "a" * 10000
        response = self.client.patch(
            "/api/items/item1",
            json={"title": long_title},
            headers={"Authorization": "Bearer token"}
        )

        # Expect 422 Unprocessable Entity (Pydantic validation error)
        self.assertEqual(response.status_code, 422)
        print("Test 1 (Update Item Title) Status Code:", response.status_code)

    @patch("main.verify_google_token")
    def test_create_note_limit(self, mock_verify):
        mock_verify.return_value = {"email": "test@example.com"}

        self.mock_db.get_shared_item = AsyncMock(return_value={"user_email": "test@example.com", "id": "item1"})
        self.mock_db.create_item_note = AsyncMock(return_value=MagicMock(id="note1", item_id="item1", user_email="test@example.com", text="test", image_path=None, created_at=None, updated_at=None))

        # Huge text
        long_text = "a" * 20000
        response = self.client.post(
            "/api/items/item1/notes",
            data={"text": long_text},
            headers={"Authorization": "Bearer token"}
        )

        # Expect 400 Bad Request (Manual check)
        self.assertEqual(response.status_code, 400)
        print("Test 2 (Create Note Text) Status Code:", response.status_code)

if __name__ == "__main__":
    unittest.main()
