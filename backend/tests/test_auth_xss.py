import unittest
import os
import sys
import importlib
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Add backend directory to path
BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.append(BACKEND_DIR)
os.chdir(BACKEND_DIR)

class TestAuthXSS(unittest.TestCase):
    def setUp(self):
        # Force Development Env
        self.env_patcher = patch.dict(os.environ, {"APP_ENV": "development"})
        self.env_patcher.start()

        # Reload main to ensure it picks up the env
        import main
        importlib.reload(main)
        from main import app

        self.client = TestClient(app)

    def tearDown(self):
        self.env_patcher.stop()

    @patch('main.oauth.google.authorize_access_token')
    def test_auth_reflected_xss(self, mock_authorize):
        """
        Test that error parameters passed to the /auth endpoint are HTML escaped
        to prevent reflected XSS.
        """
        from authlib.integrations.starlette_client import OAuthError

        # Simulate an OAuthError with a malicious payload
        malicious_payload = "<script>alert('XSS')</script>"
        mock_authorize.side_effect = OAuthError(error=malicious_payload)

        with self.client as client:
            response = client.get("/auth?error=" + malicious_payload)

            # Ensure the response is an HTML page and status is 200 (since it just returns HTML)
            self.assertEqual(response.status_code, 200)

            # The malicious payload should be escaped
            self.assertNotIn("<script>alert('XSS')</script>", response.text)
            self.assertIn("&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;", response.text)

if __name__ == '__main__':
    unittest.main()
