import unittest
import time
import os
import sys
from unittest.mock import patch

# Add backend directory to path
BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.append(BACKEND_DIR)
os.chdir(BACKEND_DIR)

from rate_limiter import RateLimiter

class TestRateLimiter(unittest.TestCase):
    def setUp(self):
        # Ensure NO_RATE_LIMIT is not set for these tests
        if "NO_RATE_LIMIT" in os.environ:
            del os.environ["NO_RATE_LIMIT"]

    def test_basic_limit(self):
        """Test that requests within limit are allowed and over limit are blocked."""
        limiter = RateLimiter(max_requests=2, window_seconds=1)
        client = "client1"

        self.assertTrue(limiter.is_allowed(client), "First request should be allowed")
        self.assertTrue(limiter.is_allowed(client), "Second request should be allowed")
        self.assertFalse(limiter.is_allowed(client), "Third request should be blocked")

    def test_window_expiry(self):
        """Test that requests are allowed again after window expires."""
        limiter = RateLimiter(max_requests=1, window_seconds=1)
        client = "client2"

        self.assertTrue(limiter.is_allowed(client), "First request should be allowed")
        self.assertFalse(limiter.is_allowed(client), "Second request should be blocked immediately")

        # Sleep longer than window
        time.sleep(1.1)
        self.assertTrue(limiter.is_allowed(client), "Request should be allowed after window expiry")

    def test_multiple_clients(self):
        """Test that limits are applied independently per client."""
        limiter = RateLimiter(max_requests=1, window_seconds=1)
        client1 = "client_A"
        client2 = "client_B"

        self.assertTrue(limiter.is_allowed(client1))
        self.assertFalse(limiter.is_allowed(client1))

        # Client 2 should still be allowed
        self.assertTrue(limiter.is_allowed(client2))

    def test_memory_protection(self):
        """Test that storage is cleared if client count exceeds limit."""
        # Using a very small max_requests but normal logic checks
        limiter = RateLimiter(max_requests=10, window_seconds=60)

        # Simulate filling up memory with many clients
        # We need to manually set requests dict size or mock it if we can't easily generate 10001
        # But we can just inject into the dict for speed
        for i in range(10001):
            limiter.requests[f"user_{i}"].append(time.time())

        # Now verify count > 10000
        self.assertGreater(len(limiter.requests), 10000)

        # Trigger check with a new request
        client = "new_client"
        limiter.is_allowed(client)

        # Check if cleared (should only contain the new client now, or be very small)
        self.assertLess(len(limiter.requests), 100)
        self.assertIn(client, limiter.requests)

    @patch.dict(os.environ, {"NO_RATE_LIMIT": "true"})
    def test_bypass_env_var(self):
        """Test that limits are bypassed when NO_RATE_LIMIT is set."""
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        # Re-init because __init__ reads env var
        limiter = RateLimiter(max_requests=1, window_seconds=60)

        client = "client_bypass"
        self.assertTrue(limiter.is_allowed(client))
        self.assertTrue(limiter.is_allowed(client)) # Should be blocked normally
        self.assertTrue(limiter.is_allowed(client))

if __name__ == '__main__':
    unittest.main()
