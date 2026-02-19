import unittest
import time
import os
import sys
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

# Setup path to import backend modules
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Ensure APP_ENV is development to avoid production checks/init
os.environ["APP_ENV"] = "development"
os.environ["SECRET_KEY"] = "test-secret"

# Import RateLimiter class
from rate_limiter import RateLimiter

# Import main app for integration verification
# We need to handle potential import errors if dependencies are missing in the test env,
# but assuming standard dev env they should be there.
try:
    import main
except ImportError:
    main = None

class TestRateLimiter(unittest.TestCase):
    def setUp(self):
        # Ensure NO_RATE_LIMIT is unset for tests unless specified
        if "NO_RATE_LIMIT" in os.environ:
            del os.environ["NO_RATE_LIMIT"]

        # Create a standalone app for logic testing
        self.app = FastAPI()

        @self.app.get("/test", dependencies=[Depends(RateLimiter(requests=2, window=1))])
        async def test_route():
            return {"status": "ok"}

        self.client = TestClient(self.app)

    def test_rate_limit_logic(self):
        """Test that requests are limited correctly."""
        # Request 1: OK
        res = self.client.get("/test")
        self.assertEqual(res.status_code, 200)

        # Request 2: OK
        res = self.client.get("/test")
        self.assertEqual(res.status_code, 200)

        # Request 3: 429
        res = self.client.get("/test")
        self.assertEqual(res.status_code, 429)
        self.assertEqual(res.json()["detail"], "Too many requests")

    def test_window_reset(self):
        """Test that limits reset after the window passes."""
        self.client.get("/test")
        self.client.get("/test")
        self.assertEqual(self.client.get("/test").status_code, 429)

        # Wait for window (1s) to pass
        time.sleep(1.1)

        res = self.client.get("/test")
        self.assertEqual(res.status_code, 200)

    def test_no_rate_limit_env(self):
        """Test that NO_RATE_LIMIT environment variable disables limits."""
        os.environ["NO_RATE_LIMIT"] = "1"
        try:
            self.client.get("/test")
            self.client.get("/test")
            res = self.client.get("/test")
            self.assertEqual(res.status_code, 200)
        finally:
            del os.environ["NO_RATE_LIMIT"]

    def test_main_routes_configured(self):
        """Verify that the main application has rate limiters configured on critical endpoints."""
        if main is None:
            self.skipTest("Could not import main module")

        def get_limiter(path, method):
            for route in main.app.routes:
                if getattr(route, "path", "") == path and method in getattr(route, "methods", []):
                    for dep in route.dependencies:
                        if isinstance(dep.dependency, RateLimiter):
                            return dep.dependency
            return None

        # /login: 10/60
        limiter = get_limiter("/login", "GET")
        self.assertIsNotNone(limiter, "/login missing RateLimiter")
        self.assertEqual(limiter.requests, 10)
        self.assertEqual(limiter.window, 60)

        # /api/share: 20/60
        limiter = get_limiter("/api/share", "POST")
        self.assertIsNotNone(limiter, "/api/share missing RateLimiter")
        self.assertEqual(limiter.requests, 20)

        # /api/items/{item_id}/notes: 20/60
        limiter = get_limiter("/api/items/{item_id}/notes", "POST")
        self.assertIsNotNone(limiter, "/api/items/{item_id}/notes missing RateLimiter")
        self.assertEqual(limiter.requests, 20)

        # /api/search: 20/60
        limiter = get_limiter("/api/search", "GET")
        self.assertIsNotNone(limiter, "/api/search missing RateLimiter")
        self.assertEqual(limiter.requests, 20)

if __name__ == "__main__":
    unittest.main()
