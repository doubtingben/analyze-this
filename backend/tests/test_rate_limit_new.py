import sys
import os
import unittest
from unittest.mock import MagicMock, patch
from fastapi import Request, HTTPException

# Add backend directory to path
BACKEND_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(BACKEND_DIR)

from rate_limiter import RateLimiter
# Need to import main to check routes, but avoid side effects if possible
# However main.py runs on import? No, code is inside functions/defs mostly,
# except for app creation and db setup.
# We need to mock database initialization to avoid errors.
with patch("database.FirestoreDatabase"), patch("database.SQLiteDatabase"):
    import main

class TestRateLimiter(unittest.IsolatedAsyncioTestCase):
    async def test_allow_request(self):
        limiter = RateLimiter(times=2, seconds=60)
        request = MagicMock(spec=Request)
        request.client.host = "127.0.0.1"
        request.headers.get.return_value = None

        await limiter(request)
        await limiter(request)
        # Should not raise

    async def test_block_request(self):
        limiter = RateLimiter(times=1, seconds=60)
        request = MagicMock(spec=Request)
        request.client.host = "127.0.0.1"
        request.headers.get.return_value = None

        await limiter(request)

        with self.assertRaises(HTTPException) as cm:
            await limiter(request)
        self.assertEqual(cm.exception.status_code, 429)

    async def test_window_reset(self):
        limiter = RateLimiter(times=1, seconds=1)
        request = MagicMock(spec=Request)
        request.client.host = "127.0.0.1"
        request.headers.get.return_value = None

        await limiter(request)

        # Simulate time passing
        import time
        with patch("time.time", return_value=time.time() + 2):
            await limiter(request) # Should succeed now

    async def test_bypass_env(self):
        # Create a new instance while env var is set
        with patch.dict("os.environ", {"NO_RATE_LIMIT": "1"}):
            limiter = RateLimiter(times=1, seconds=60)
            self.assertFalse(limiter.enabled)

            request = MagicMock(spec=Request)
            request.client.host = "127.0.0.1"

            await limiter(request)
            await limiter(request) # Should pass even if limit is 1

    async def test_x_forwarded_for(self):
        limiter = RateLimiter(times=1, seconds=60)
        request = MagicMock(spec=Request)
        request.client.host = "127.0.0.1"
        request.headers.get.side_effect = lambda k: "10.0.0.1, 127.0.0.1" if k == "X-Forwarded-For" else None

        # First request from 10.0.0.1
        await limiter(request)

        # Second request from same IP should fail
        with self.assertRaises(HTTPException):
            await limiter(request)

    def test_routes_configured(self):
        """Verify that sensitive routes have RateLimiter configured."""
        from fastapi.routing import APIRoute

        # path -> (method, limit)
        routes_to_check = {
            "/login": ("GET", 5),
            "/api/share": ("POST", 20),
            "/api/items/{item_id}/notes": ("POST", 20),
            "/api/search": ("GET", 20)
        }

        found = 0
        for route in main.app.routes:
            if isinstance(route, APIRoute) and route.path in routes_to_check:
                expected_method, limit = routes_to_check[route.path]
                if expected_method in route.methods:
                    # Check dependencies
                    has_limiter = False
                    for dep in route.dependencies:
                        # dep.dependency is the callable.
                        # If it's a RateLimiter instance...
                        if isinstance(dep.dependency, RateLimiter):
                            self.assertEqual(dep.dependency.times, limit, f"Route {route.path} has wrong limit")
                            has_limiter = True
                    self.assertTrue(has_limiter, f"Route {route.path} {expected_method} missing RateLimiter")
                    found += 1

        self.assertEqual(found, len(routes_to_check), "Not all routes found")

if __name__ == "__main__":
    unittest.main()
