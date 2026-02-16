import sys
import os
import unittest
import time
from fastapi.testclient import TestClient

# Add backend directory to path
BACKEND_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

from rate_limiter import RateLimiter, limiter

# Ensure development mode for tests
os.environ["APP_ENV"] = "development"

class TestRateLimiter(unittest.TestCase):
    def setUp(self):
        limiter.reset()

    def test_rate_limiter_logic(self):
        test_limiter = RateLimiter()
        ip = "127.0.0.1"
        key = "test"
        limit = 2
        window = 1

        # First request: Allowed
        self.assertTrue(test_limiter.is_allowed(ip, key, limit, window))

        # Second request: Allowed
        self.assertTrue(test_limiter.is_allowed(ip, key, limit, window))

        # Third request: Blocked
        self.assertFalse(test_limiter.is_allowed(ip, key, limit, window))

        # Wait for window to expire
        time.sleep(1.1)

        # Fourth request: Allowed (reset)
        self.assertTrue(test_limiter.is_allowed(ip, key, limit, window))

    def test_rate_limiter_distinct_ips(self):
        test_limiter = RateLimiter()
        key = "test"
        limit = 1
        window = 60

        self.assertTrue(test_limiter.is_allowed("1.1.1.1", key, limit, window))
        self.assertFalse(test_limiter.is_allowed("1.1.1.1", key, limit, window))

        self.assertTrue(test_limiter.is_allowed("2.2.2.2", key, limit, window))

    def test_rate_limiter_distinct_keys(self):
        test_limiter = RateLimiter()
        ip = "1.1.1.1"
        limit = 1
        window = 60

        self.assertTrue(test_limiter.is_allowed(ip, "key1", limit, window))
        self.assertFalse(test_limiter.is_allowed(ip, "key1", limit, window))

        self.assertTrue(test_limiter.is_allowed(ip, "key2", limit, window))


class TestRateLimitIntegration(unittest.TestCase):
    def setUp(self):
        import main
        self.app = main.app
        self.client = TestClient(self.app)
        limiter.reset()

    def test_login_rate_limit(self):
        # /login has limit=10
        # Send 10 requests
        for _ in range(10):
            response = self.client.get("/login", follow_redirects=False)
            # 307 or 200 depending on redirect behavior, but NOT 429
            self.assertNotEqual(response.status_code, 429)

        # 11th request should be blocked
        response = self.client.get("/login", follow_redirects=False)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json(), {"detail": "Too many requests"})

    def test_x_forwarded_for(self):
        headers = {"X-Forwarded-For": "10.0.0.1"}

        # Exhaust limit for 10.0.0.1
        for _ in range(10):
            self.client.get("/login", headers=headers, follow_redirects=False)

        response = self.client.get("/login", headers=headers, follow_redirects=False)
        self.assertEqual(response.status_code, 429)

        # Another IP should work
        headers2 = {"X-Forwarded-For": "10.0.0.2"}
        response = self.client.get("/login", headers=headers2, follow_redirects=False)
        self.assertNotEqual(response.status_code, 429)

if __name__ == "__main__":
    unittest.main()
