import unittest
import os
import sys
import shutil
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import Request, HTTPException

# Add backend directory to path
BACKEND_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(BACKEND_DIR)
os.chdir(BACKEND_DIR)

# Mock Environment
os.environ["APP_ENV"] = "development"
os.environ["SECRET_KEY"] = "test-secret"

import main
from main import app, check_csrf, CSRF_KEY

class TestCSRF(unittest.TestCase):
    def setUp(self):
        # Mock the DB
        self.mock_db = AsyncMock()
        main.db = self.mock_db
        self.client = TestClient(app)

    def tearDown(self):
        # Cleanup uploads created by tests
        upload_dir = os.path.join(BACKEND_DIR, "static", "uploads", "test@example.com")
        if os.path.exists(upload_dir):
            shutil.rmtree(upload_dir)

    def test_check_csrf_logic(self):
        """Unit test for the check_csrf dependency logic."""

        # Case 1: Bearer Token (Should Pass)
        req = MagicMock(spec=Request)
        req.headers = {"Authorization": "Bearer some-token"}
        req.session = {}
        # Since check_csrf is async
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(check_csrf(req))
        loop.close()

        # Case 2: Session exists, Token matches (Should Pass)
        req = MagicMock(spec=Request)
        req.headers = {"X-CSRF-Token": "secret-token"}
        req.session = {"user": "exists", CSRF_KEY: "secret-token"}

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(check_csrf(req))
        loop.close()

        # Case 3: Session exists, Header missing (Should Fail)
        req = MagicMock(spec=Request)
        req.headers = {}
        req.session = {"user": "exists", CSRF_KEY: "secret-token"}

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        with self.assertRaises(HTTPException) as cm:
            loop.run_until_complete(check_csrf(req))
        self.assertEqual(cm.exception.status_code, 403)
        loop.close()

        # Case 4: Session exists, Token mismatch (Should Fail)
        req = MagicMock(spec=Request)
        req.headers = {"X-CSRF-Token": "wrong-token"}
        req.session = {"user": "exists", CSRF_KEY: "secret-token"}

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        with self.assertRaises(HTTPException) as cm:
             loop.run_until_complete(check_csrf(req))
        self.assertEqual(cm.exception.status_code, 403)
        loop.close()

    @patch("main.oauth.google.authorize_access_token")
    def test_integration_flow(self, mock_auth):
        """Integration test with session creation."""
        # Setup mock to return user info
        mock_auth.return_value = {"userinfo": {"email": "test@example.com", "name": "Test"}}

        # 1. Login to establish session
        # We need to use AsyncMock for the awaitable
        mock_auth.side_effect = AsyncMock(return_value={"userinfo": {"email": "test@example.com", "name": "Test"}})

        # Hit /auth to get session cookie
        response = self.client.get("/auth")
        self.assertEqual(response.status_code, 200, "Auth redirect should succeed")

        # Verify DB upsert was called
        self.mock_db.upsert_user.assert_called_once()

        # Verify CSRF cookie is present
        self.assertIn("csrf_token", self.client.cookies)
        csrf_token = self.client.cookies["csrf_token"]

        # 2. Try POST /api/share with Session but NO Header

        # Mock database calls for share_item
        self.mock_db.create_shared_item.return_value = None
        self.mock_db.enqueue_worker_job.return_value = None

        # Request without CSRF header
        # Use files to trigger multipart/form-data
        response = self.client.post(
            "/api/share",
            data={"title": "Attack", "content": "ignored", "type": "file"},
            files={"file": ("empty.txt", b"content", "text/plain")},
            # No X-CSRF-Token header
        )
        self.assertEqual(response.status_code, 403, "Should fail without CSRF header")

        # Request WITH CSRF header
        response = self.client.post(
            "/api/share",
            data={"title": "Safe", "content": "ignored", "type": "file"},
            files={"file": ("empty.txt", b"content", "text/plain")},
            headers={"X-CSRF-Token": csrf_token}
        )
        self.assertEqual(response.status_code, 200, "Should succeed with CSRF header")

if __name__ == "__main__":
    unittest.main()
