import unittest
import os
import sys
import importlib
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

# Add backend directory to path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Mock external services
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()
sys.modules["firebase_admin.storage"] = MagicMock()

# Ensure we force enable rate limits
os.environ["NO_RATE_LIMIT"] = "false"
os.environ["APP_ENV"] = "development"

# Reload modules to apply env vars
import rate_limiter
importlib.reload(rate_limiter)
import main
importlib.reload(main)

class TestRateLimit(unittest.TestCase):
    def setUp(self):
        # Mock database object to avoid actual DB calls and issues with None
        self.mock_db = MagicMock()
        # Ensure async methods are AsyncMock
        self.mock_db.create_shared_item = AsyncMock(return_value=True)
        self.mock_db.enqueue_worker_job = AsyncMock(return_value=True)
        self.mock_db.validate_user_item_ownership = AsyncMock(return_value=["item1"])

        # Patch the global db variable in main
        self.db_patcher = patch("main.db", self.mock_db)
        self.db_patcher.start()

        self.client = TestClient(main.app)

    def tearDown(self):
        self.db_patcher.stop()

    def test_login_rate_limit(self):
        ip = "1.1.1.1"
        headers = {"X-Forwarded-For": ip}

        with patch("main.oauth.google.authorize_redirect") as mock_redirect:
            mock_redirect.return_value = "mock_redirect"

            for i in range(10):
                response = self.client.get("/login", headers=headers, follow_redirects=False)
                if response.status_code == 429:
                    break

            self.assertEqual(response.status_code, 429, "Should be blocked eventually")

    def test_share_rate_limit(self):
        ip = "2.2.2.2"
        headers = {"X-Forwarded-For": ip, "Authorization": "Bearer dev-token"}

        with patch("main.verify_google_token", return_value={"email": "test@example.com"}):
            payload = {"title": "test", "content": "test", "type": "text"}

            for i in range(30):
                response = self.client.post("/api/share", json=payload, headers=headers)
                if response.status_code == 429:
                    break

            self.assertEqual(response.status_code, 429, "Should be blocked eventually")

    def test_x_forwarded_for_precedence(self):
        ip = "3.3.3.3"
        headers = {"X-Forwarded-For": ip}

        with patch("main.oauth.google.authorize_redirect") as mock_redirect:
             mock_redirect.return_value = "ok"

             # Exhaust limit for 3.3.3.3
             # We assume it takes 3-5 requests
             for _ in range(6):
                 self.client.get("/login", headers=headers, follow_redirects=False)

             # Should be blocked
             response = self.client.get("/login", headers=headers, follow_redirects=False)
             self.assertEqual(response.status_code, 429)

             # But request from same client (127.0.0.1) but different X-Forwarded-For should succeed
             headers2 = {"X-Forwarded-For": "4.4.4.4"}
             response = self.client.get("/login", headers=headers2, follow_redirects=False)
             self.assertNotEqual(response.status_code, 429)

if __name__ == "__main__":
    unittest.main()
