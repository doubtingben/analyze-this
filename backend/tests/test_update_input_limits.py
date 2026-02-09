
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

class TestUpdateInputLimits(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        # Mock DB methods
        self.patcher = patch("main.db")
        self.mock_db = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    @patch("main.verify_google_token")
    def test_update_item_tags_limit(self, mock_verify):
        mock_verify.return_value = {"email": "test@example.com"}

        # Mock DB Item
        self.mock_db.get_shared_item = AsyncMock(return_value={"user_email": "test@example.com", "id": "item1", "analysis": {}})
        self.mock_db.update_shared_item = AsyncMock(return_value=True)

        # Huge number of tags
        many_tags = ["tag" + str(i) for i in range(100)]
        response = self.client.patch(
            "/api/items/item1",
            json={"tags": many_tags},
            headers={"Authorization": "Bearer token"}
        )

        # Expect 422 Unprocessable Entity
        self.assertEqual(response.status_code, 422, "Should fail with too many tags")

        # Long tag
        long_tag = ["a" * 1000]
        response = self.client.patch(
            "/api/items/item1",
            json={"tags": long_tag},
            headers={"Authorization": "Bearer token"}
        )
        self.assertEqual(response.status_code, 422, "Should fail with long tag")

    @patch("main.verify_google_token")
    def test_update_item_follow_up_limit(self, mock_verify):
        mock_verify.return_value = {"email": "test@example.com"}

        self.mock_db.get_shared_item = AsyncMock(return_value={"user_email": "test@example.com", "id": "item1"})
        self.mock_db.update_shared_item = AsyncMock(return_value=True)

        # Huge follow_up
        long_follow_up = "a" * 20000
        response = self.client.patch(
            "/api/items/item1",
            json={"follow_up": long_follow_up},
            headers={"Authorization": "Bearer token"}
        )

        self.assertEqual(response.status_code, 422, "Should fail with long follow_up")

    @patch("main.verify_google_token")
    def test_update_item_next_step_limit(self, mock_verify):
        mock_verify.return_value = {"email": "test@example.com"}

        self.mock_db.get_shared_item = AsyncMock(return_value={"user_email": "test@example.com", "id": "item1"})
        self.mock_db.update_shared_item = AsyncMock(return_value=True)

        # Huge next_step
        long_next_step = "a" * 1000
        response = self.client.patch(
            "/api/items/item1",
            json={"next_step": long_next_step},
            headers={"Authorization": "Bearer token"}
        )

        self.assertEqual(response.status_code, 422, "Should fail with long next_step")
