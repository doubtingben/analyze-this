import sys
import os
import time
import asyncio
import unittest
from unittest.mock import MagicMock, patch

# 1. Setup Environment and Mocks BEFORE importing main
os.environ["APP_ENV"] = "production"

# Mock firebase_admin to avoid init errors
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.storage"] = MagicMock()
sys.modules["google.oauth2"] = MagicMock()
sys.modules["google.oauth2.id_token"] = MagicMock()

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
import main

# 2. Setup Benchmark Logic
class BenchmarkBlocking(unittest.TestCase):
    def setUp(self):
        self.auth_patcher = patch('main.verify_google_token')
        self.mock_verify = self.auth_patcher.start()
        self.mock_verify.return_value = {
            "email": "test@example.com",
            "name": "Test User",
            "picture": "http://example.com/pic"
        }

        self.storage_patcher = patch('main.storage')
        self.mock_storage = self.storage_patcher.start()

        self.mock_bucket = MagicMock()
        self.mock_blob = MagicMock()
        self.mock_storage.bucket.return_value = self.mock_bucket
        self.mock_bucket.blob.return_value = self.mock_blob

        # Simulate blocking download
        def slow_download():
            time.sleep(0.5)
            return b"fake content"

        self.mock_blob.download_as_bytes.side_effect = slow_download
        self.mock_blob.content_type = "text/plain"

    def tearDown(self):
        self.auth_patcher.stop()
        self.storage_patcher.stop()

    def test_blocking_behavior(self):
        async def run_benchmark():
            from httpx import AsyncClient, ASGITransport

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:

                # We wrap the request in a task that measures its own duration relative to a common start
                start_time = time.time()

                async def make_request(url, headers=None, name=""):
                    # We wait a tiny bit to ensure we are running "together"
                    # But actually we want to see if the loop is blocked.
                    req_start = time.time()
                    await client.get(url, headers=headers)
                    req_end = time.time()
                    duration = req_end - start_time # Time from GLOBAL start
                    print(f"{name} finished at T+{duration:.4f}s")
                    return duration

                # Schedule both
                # Note: asyncio.gather schedules them.
                # If the first one blocks the loop immediately, the second one won't start until the first one returns.
                t1_coro = make_request("/api/content/uploads/test@example.com/file.txt", headers={"Authorization": "Bearer token"}, name="BlockingTask")
                t2_coro = make_request("/api/version", name="FastTask")

                results = await asyncio.gather(t1_coro, t2_coro)
                blocking_duration, fast_duration = results

                return blocking_duration, fast_duration

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        blocking_duration, fast_duration = loop.run_until_complete(run_benchmark())
        loop.close()

        print(f"Blocking Task Duration: {blocking_duration:.4f}s")
        print(f"Fast Task Duration: {fast_duration:.4f}s")

        # Assertion
        # If blocked, Fast Task will finish LATE (near 0.5s)
        # If fixed, Fast Task will finish EARLY (near 0.0s)

        # We assert that Fast Task is indeed slow in this reproduction
        # This confirms the issue.
        if fast_duration > 0.4:
            print("CONFIRMED: Event loop was blocked.")
        else:
            print("Event loop was NOT blocked.")

        # Ensure that with the fix, the fast task is indeed fast
        # We allow a small buffer (e.g., 0.1s) for overhead, but it should be much less than the 0.5s blocking time
        self.assertLess(fast_duration, 0.2, "Event loop appears to be blocked! Fast task took too long.")

        return fast_duration

if __name__ == '__main__':
    unittest.main()
