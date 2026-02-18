import unittest
import time
import os
import sys
from unittest.mock import patch

# Add backend directory to path
BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

from rate_limiter import RateLimiter

class TestRateLimiter(unittest.TestCase):
    def setUp(self):
        # Start a patcher for os.environ to ensure clean state
        self.env_patcher = patch.dict(os.environ, {}, clear=True)
        self.env_patcher.start()
        self.limiter = RateLimiter(limit=2, window_seconds=10)

    def tearDown(self):
        self.env_patcher.stop()

    def test_allow_requests_within_limit(self):
        self.assertTrue(self.limiter.is_allowed("user1"))
        self.assertTrue(self.limiter.is_allowed("user1"))

    def test_block_requests_exceeding_limit(self):
        self.assertTrue(self.limiter.is_allowed("user1"))
        self.assertTrue(self.limiter.is_allowed("user1"))
        self.assertFalse(self.limiter.is_allowed("user1"))

    def test_separate_keys(self):
        self.assertTrue(self.limiter.is_allowed("user1"))
        self.assertTrue(self.limiter.is_allowed("user1"))
        self.assertFalse(self.limiter.is_allowed("user1"))

        # user2 should still be allowed
        self.assertTrue(self.limiter.is_allowed("user2"))

    @patch('rate_limiter.time.time')
    def test_window_reset(self, mock_time):
        mock_time.return_value = 1000.0

        # Re-create limiter to ensure it uses the current time (though is_allowed uses time.time)
        # But we want to ensure limit=1 for this test
        self.limiter = RateLimiter(limit=1, window_seconds=10)

        self.assertTrue(self.limiter.is_allowed("user1"))
        self.assertFalse(self.limiter.is_allowed("user1"))

        # Advance time past window (10s)
        mock_time.return_value = 1011.0
        self.assertTrue(self.limiter.is_allowed("user1"))

    def test_memory_protection(self):
        self.limiter = RateLimiter(limit=10, window_seconds=60)
        # Fill with many keys
        for i in range(10005):
            self.limiter.is_allowed(f"user_{i}")

        # Should have cleared and started over
        self.assertLess(len(self.limiter.requests), 10000)

    def test_no_rate_limit_env(self):
        # We need to stop the global patcher to set specific env var
        self.env_patcher.stop()
        try:
            with patch.dict(os.environ, {'NO_RATE_LIMIT': 'true'}):
                limiter = RateLimiter(limit=1, window_seconds=10)
                self.assertTrue(limiter.is_allowed("user1"))
                self.assertTrue(limiter.is_allowed("user1")) # Should be allowed despite limit 1
        finally:
            self.env_patcher.start()

if __name__ == '__main__':
    unittest.main()
