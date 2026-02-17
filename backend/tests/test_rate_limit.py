import unittest
from unittest.mock import MagicMock, patch
import os
import sys
import time
import asyncio
from collections import deque

# Set ENV for testing
os.environ["APP_ENV"] = "development"
os.environ["SECRET_KEY"] = "test-secret"

# Mock firebase_admin modules to avoid init errors
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.storage"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()

# Add backend to path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

from fastapi.testclient import TestClient
from fastapi import HTTPException, Request
from main import app
from rate_limiter import RateLimiter

class TestRateLimit(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        # Note: RateLimiter instances are created at app startup in decorators.
        # Their state (self.clients) persists across tests in this process.
        # To avoid flakiness, we should try to reset them or use unique IPs.
        # Since we can't easily access the instances attached to routes,
        # we will rely on the fact that these tests run sequentially and
        # we can just exhaust the limit.

    def test_rate_limiter_class_logic(self):
        """Test the RateLimiter logic in isolation."""
        limiter = RateLimiter(requests_limit=5, time_window=1)
        request = MagicMock()
        request.client.host = "127.0.0.1"

        async def call_limiter():
            await limiter(request)

        loop = asyncio.new_event_loop()
        try:
            # Should pass 5 times
            for _ in range(5):
                loop.run_until_complete(call_limiter())

            # 6th time should fail
            with self.assertRaises(HTTPException) as cm:
                loop.run_until_complete(call_limiter())
            self.assertEqual(cm.exception.status_code, 429)
        finally:
            loop.close()

    def test_memory_protection(self):
        """Test that RateLimiter clears memory if too many clients."""
        limiter = RateLimiter(requests_limit=10, time_window=60)

        # Fill with 10001 clients
        # We simulate this by accessing self.clients directly
        for i in range(10001):
            limiter.clients[f"ip_{i}"] = deque([time.time()])

        self.assertGreater(len(limiter.clients), 10000)

        # Next request should trigger clear
        request = MagicMock()
        request.client.host = "new_ip"

        async def call_limiter():
            await limiter(request)

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(call_limiter())
        finally:
            loop.close()

        # Should have cleared old clients and added the new one
        self.assertEqual(len(limiter.clients), 1)
        self.assertIn("new_ip", limiter.clients)

    def test_login_rate_limit(self):
        """Test /login rate limit integration."""
        # /login has limit 10/60s
        # Note: TestClient uses 'testclient' as host by default.
        # If other tests ran, this might be pre-filled.

        # We'll just run until we hit 429
        max_attempts = 15
        hit_limit = False

        for _ in range(max_attempts):
            response = self.client.get("/login", follow_redirects=False)
            if response.status_code == 429:
                hit_limit = True
                break

        self.assertTrue(hit_limit, "Should have hit rate limit for /login")

    def test_share_rate_limit(self):
        """Test /api/share rate limit."""
        # Limit 20/60s
        headers = {"Authorization": "Bearer dev-token"}

        with patch("main.verify_google_token") as mock_verify:
            mock_verify.return_value = {"email": "test@example.com"}

            hit_limit = False
            # Hit up to 25 times (20 is limit)
            for _ in range(25):
                # We need to send valid data to avoid 400/422 before rate limit?
                # Rate limit dependency is usually checked first or early.
                # But let's send minimal valid data
                response = self.client.post(
                    "/api/share",
                    headers=headers,
                    data={"title": "test", "content": "test", "type": "text"}
                )
                if response.status_code == 429:
                    hit_limit = True
                    break

            self.assertTrue(hit_limit, "Should have hit rate limit for /api/share")

if __name__ == "__main__":
    unittest.main()
