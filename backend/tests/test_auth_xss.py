import unittest
import os
import sys
import importlib
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

# Add backend directory to path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)
os.chdir(BACKEND_DIR)

from authlib.integrations.starlette_client import OAuthError

class TestAuthXSS(unittest.TestCase):
    def setUp(self):
        # Force Development Env
        self.env_patcher = patch.dict(os.environ, {"APP_ENV": "development"})
        self.env_patcher.start()

        # Reload main to ensure it picks up the env
        import main
        importlib.reload(main)
        from main import app

        # Mock the DB interface
        self.mock_db = MagicMock()
        main.db = self.mock_db

        self.client = TestClient(app)

    def tearDown(self):
        self.env_patcher.stop()

    def test_auth_error_xss(self):
        """
        Test that OAuth errors are properly HTML escaped to prevent Reflected XSS.
        """
        xss_payload = "<script>alert(1)</script>"

        with patch("main.oauth.google.authorize_access_token") as mock_token:
            mock_token.side_effect = OAuthError(error=xss_payload)

            # Hit auth endpoint
            response = self.client.get("/auth?error=" + xss_payload)

            self.assertEqual(response.status_code, 200)
            self.assertNotIn("<script>", response.text)
            self.assertIn("&lt;script&gt;", response.text)
            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", response.text)

if __name__ == '__main__':
    unittest.main()
