import sys
import os
import unittest
import time
import asyncio
from unittest.mock import MagicMock
from fastapi import Request, HTTPException

# Add backend directory to path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from rate_limiter import RateLimiter

class TestRateLimiter(unittest.TestCase):
    def setUp(self):
        # Ensure NO_RATE_LIMIT is false for these tests
        os.environ["NO_RATE_LIMIT"] = "false"

    def tearDown(self):
        if "NO_RATE_LIMIT" in os.environ:
            del os.environ["NO_RATE_LIMIT"]

    def create_mock_request(self, ip="127.0.0.1", forwarded_for=None):
        request = MagicMock(spec=Request)
        request.client = MagicMock()
        request.client.host = ip
        request.headers = {}
        if forwarded_for:
            request.headers["X-Forwarded-For"] = forwarded_for
        return request

    def test_rate_limit_enforcement(self):
        # 5 requests per 10 seconds
        limiter = RateLimiter(max_calls=5, time_frame=10)
        request = self.create_mock_request()

        # Should allow 5 calls
        for _ in range(5):
            asyncio.run(limiter(request))

        # 6th call should fail
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(limiter(request))
        self.assertEqual(cm.exception.status_code, 429)

    def test_window_expiration(self):
        # 2 requests per 1 second
        limiter = RateLimiter(max_calls=2, time_frame=1)
        request = self.create_mock_request()

        asyncio.run(limiter(request))
        asyncio.run(limiter(request))

        # Should fail immediately
        with self.assertRaises(HTTPException):
            asyncio.run(limiter(request))

        # Wait for window to expire
        time.sleep(1.1)

        # Should succeed now
        asyncio.run(limiter(request))

    def test_ip_separation(self):
        limiter = RateLimiter(max_calls=1, time_frame=10)
        req1 = self.create_mock_request(ip="1.1.1.1")
        req2 = self.create_mock_request(ip="2.2.2.2")

        asyncio.run(limiter(req1)) # IP 1 uses quota

        # IP 1 blocked
        with self.assertRaises(HTTPException):
            asyncio.run(limiter(req1))

        # IP 2 allowed (independent quota)
        asyncio.run(limiter(req2))

    def test_forwarded_for_header(self):
        limiter = RateLimiter(max_calls=1, time_frame=10)
        # Request looks like it comes from Load Balancer, but X-Forwarded-For has real IP
        req = self.create_mock_request(ip="10.0.0.1", forwarded_for="203.0.113.1, 10.0.0.1")

        asyncio.run(limiter(req))

        # Should be blocked for the same real IP
        req_same = self.create_mock_request(ip="10.0.0.2", forwarded_for="203.0.113.1")
        with self.assertRaises(HTTPException):
            asyncio.run(limiter(req_same))

        # Different real IP should be allowed
        req_diff = self.create_mock_request(ip="10.0.0.1", forwarded_for="203.0.113.2")
        asyncio.run(limiter(req_diff))

    def test_bypass_env_var(self):
        os.environ["NO_RATE_LIMIT"] = "true"
        limiter = RateLimiter(max_calls=1, time_frame=10)
        request = self.create_mock_request()

        # Should allow infinite calls
        for _ in range(10):
            asyncio.run(limiter(request))

        # Reset
        os.environ["NO_RATE_LIMIT"] = "false"

if __name__ == "__main__":
    unittest.main()
