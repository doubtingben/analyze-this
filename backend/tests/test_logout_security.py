import unittest
import os
import sys
from unittest.mock import patch, AsyncMock
import json
import base64

# Force env BEFORE importing main
os.environ["APP_ENV"] = "development"
os.environ["SECRET_KEY"] = "dev-secret"

from fastapi.testclient import TestClient

# Add backend directory to path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BACKEND_DIR)
os.chdir(BACKEND_DIR)

import main
from database import SQLiteDatabase
main.db = SQLiteDatabase()
from main import app, CSRF_KEY

class TestLogoutSecurity(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("main.oauth.google.authorize_access_token")
    def test_logout_clears_session(self, mock_auth):
        # Mock auth to create a session
        mock_auth.return_value = {"userinfo": {"email": "test@example.com", "name": "Test"}}
        main.db.upsert_user = AsyncMock()
        main.db.get_shared_items = AsyncMock(return_value=[])

        # 1. Login
        self.client.get("/auth")

        # 2. Hit an endpoint to make sure session has `user` and `csrf_token`
        self.client.get("/")

        # 3. Logout
        self.client.get("/logout")

        session_cookie_after = self.client.cookies.get("session")
        if session_cookie_after:
            # Decode payload
            payload = session_cookie_after.split(".")[0]
            # Add padding
            payload += "=" * ((4 - len(payload) % 4) % 4)
            decoded = json.loads(base64.urlsafe_b64decode(payload).decode())

            # Since request.session.clear() wasn't used, CSRF token or other state might remain
            self.assertNotIn("csrf_token", decoded, "Session state pollution: CSRF token was not cleared during logout")

if __name__ == '__main__':
    unittest.main()
