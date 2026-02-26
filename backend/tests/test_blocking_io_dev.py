import sys
import os
import time
import asyncio
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Force APP_ENV to development BEFORE importing main
os.environ["APP_ENV"] = "development"
os.environ["SECRET_KEY"] = "dev-secret-key"

# Mock firebase_admin and other deps to avoid init errors
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.storage"] = MagicMock()
sys.modules["google.oauth2"] = MagicMock()
sys.modules["google.oauth2.id_token"] = MagicMock()

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import the function under test
# We import main after setting env vars and mocking
import main
from main import _read_user_blob

class TestBlockingDev(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Create a temporary directory structure for the test
        self.test_dir = Path("static/uploads/test@example.com")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.test_file = self.test_dir / "test.txt"
        self.test_file.touch()

    async def asyncTearDown(self):
        # Clean up
        if self.test_file.exists():
            self.test_file.unlink()
        if self.test_dir.exists():
            self.test_dir.rmdir()

    async def test_blocking_read(self):
        # We want to intercept read_bytes specifically for our test file path
        # But patching Path.read_bytes globally is easiest given the implementation creates new Path objects inside

        original_read_bytes = Path.read_bytes

        # Capture test_file path for use in the closure
        target_file_path = str(self.test_file.resolve())

        def slow_read_bytes(path_obj):
            # path_obj is the Path instance
            # Only slow down for our specific test file to avoid side effects
            try:
                if str(path_obj.resolve()) == target_file_path:
                    time.sleep(0.5)
                    return b"fake content"
            except Exception:
                pass
            return original_read_bytes(path_obj)

        with patch("pathlib.Path.read_bytes", side_effect=slow_read_bytes, autospec=True):

            # Define a fast task
            async def fast_task():
                t0 = time.time()
                # Sleep long enough for slow_task to start and block, but shorter than the block duration
                await asyncio.sleep(0.1)
                t1 = time.time()
                return t1 - t0

            # Define the slow task (calling the function under test)
            async def slow_task():
                # Yield initially to let fast_task start its sleep
                await asyncio.sleep(0.01)
                user_email = "test@example.com"
                blob_path = f"uploads/{user_email}/test.txt"
                return await _read_user_blob(blob_path, user_email)

            # Run concurrently
            start_global = time.time()
            task1 = asyncio.create_task(slow_task())
            task2 = asyncio.create_task(fast_task())

            # Wait for both
            results = await asyncio.gather(task1, task2)
            blob_content = results[0]
            fast_duration = results[1]

            print(f"Fast task took: {fast_duration:.4f}s")

            # If blocking, fast_duration will be > 0.5s because the loop is blocked by slow_read_bytes
            # If non-blocking (fixed), fast_duration will be ~0.01s (or slightly more due to overhead)

            self.assertTrue(blob_content == b"fake content", "Blob content should be returned correctly")

            # Assert that the fast task was NOT blocked significantly
            # If blocking occurred, it would take ~0.5s + overhead
            # With fix, it should take ~0.1s + overhead
            self.assertLess(fast_duration, 0.2, "Event loop appears to be blocked! Fast task took too long.")

            # return fast_duration

if __name__ == "__main__":
    unittest.main()
