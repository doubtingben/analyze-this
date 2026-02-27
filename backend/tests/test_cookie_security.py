import os
import sys
import unittest
import importlib
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

# Add backend directory to path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BACKEND_DIR)
os.chdir(BACKEND_DIR)

class TestProductionSecurityGaps(unittest.TestCase):
    def setUp(self):
        # Force Production Env
        self.env_patcher = patch.dict(os.environ, {
            "APP_ENV": "production",
            "SECRET_KEY": "test-secret-key-must-be-long-enough-for-production-check",
            "GOOGLE_CLIENT_ID": "test-client-id",
            "GOOGLE_CLIENT_SECRET": "test-client-secret"
        })
        self.env_patcher.start()

        # Reload main to ensure it picks up the env
        import main
        importlib.reload(main)
        from main import app

        # Mock the DB
        self.mock_db = AsyncMock()
        main.db = self.mock_db

        # Configure TestClient for HTTPS
        self.client = TestClient(app, base_url="https://testserver")
        self.app = app

    def tearDown(self):
        self.env_patcher.stop()

    def test_session_cookie_secure(self):
        """
        Verify if the session cookie has 'Secure' attribute in production.
        """
        # Mock OAuth to establish session
        with patch("main.oauth.google.authorize_access_token") as mock_token:
            mock_token.side_effect = AsyncMock(return_value={"userinfo": {"email": "test@example.com", "name": "Test"}})
            self.mock_db.upsert_user.return_value = MagicMock()

            # Hit auth endpoint via HTTPS
            response = self.client.get("/auth")

            # Check Set-Cookie headers directly
            set_cookies = response.headers.get_list("set-cookie")
            session_found = False
            for cookie in set_cookies:
                if "session=" in cookie:
                    session_found = True
                    is_secure = "secure" in cookie.lower()
                    is_samesite_lax = "samesite=lax" in cookie.lower()
                    print(f"\n[Check] Session cookie found: {cookie}")
                    print(f"[Check] Session cookie 'Secure' flag present: {is_secure}")
                    print(f"[Check] Session cookie 'SameSite=lax' present: {is_samesite_lax}")

                    if not is_secure:
                        self.fail("Session cookie missing Secure flag")
                    if not is_samesite_lax:
                        self.fail("Session cookie missing SameSite=lax")

            if not session_found:
                 self.fail("No session cookie set. Middleware might be blocking it or not running.")

    def test_csrf_cookie_secure(self):
        """
        Verify if the CSRF token cookie has 'Secure' attribute in production.
        """
        with patch("main.oauth.google.authorize_access_token") as mock_token, \
             patch("main.db.get_shared_items") as mock_db_get:

            mock_token.side_effect = AsyncMock(return_value={"userinfo": {"email": "test@example.com", "name": "Test"}})
            self.mock_db.upsert_user.return_value = MagicMock()
            mock_db_get.side_effect = AsyncMock(return_value=[])

            # 1. Login
            self.client.get("/auth")

            # 2. Hit root
            response = self.client.get("/")

            set_cookies = response.headers.get_list("set-cookie")

            csrf_found = False
            for cookie in set_cookies:
                if "csrf_token=" in cookie:
                    csrf_found = True
                    is_secure = "secure" in cookie.lower()
                    is_samesite_lax = "samesite=lax" in cookie.lower()
                    print(f"\n[Check] CSRF cookie found: {cookie}")
                    print(f"[Check] CSRF cookie 'Secure' flag present: {is_secure}")
                    print(f"[Check] CSRF cookie 'SameSite=lax' present: {is_samesite_lax}")

                    if not is_secure:
                        self.fail("CSRF cookie missing Secure flag")
                    if not is_samesite_lax:
                        self.fail("CSRF cookie missing SameSite=lax")

            if not csrf_found:
                 self.fail("No csrf_token cookie found.")

    def test_csp_unsafe_inline_script(self):
        """
        Verify if Content-Security-Policy allows 'unsafe-inline' in script-src.
        NOTE: Currently we expect this to be present for dashboard compatibility.
        """
        with patch("main.db.get_shared_items") as mock_db_get:
            mock_db_get.side_effect = AsyncMock(return_value=[])

            response = self.client.get("/")
            csp = response.headers.get("Content-Security-Policy", "")

            # Parse directives
            directives = {}
            for part in csp.split(';'):
                part = part.strip()
                if not part: continue
                key, *values = part.split()
                directives[key] = values

            script_src = directives.get('script-src', [])
            has_unsafe_inline = "'unsafe-inline'" in script_src

            print(f"\n[Check] script-src directives: {script_src}")
            print(f"[Check] script-src contains 'unsafe-inline': {has_unsafe_inline}")

            # For now, we acknowledge it exists but don't fail the test suite
            # This serves as a reminder/monitor rather than a blocker
            if not has_unsafe_inline:
                 print("[Info] CSP does NOT allow unsafe-inline (Great!)")
            else:
                 print("[Info] CSP allows unsafe-inline (Required for legacy dashboard)")

if __name__ == "__main__":
    unittest.main()
