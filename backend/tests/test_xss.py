import unittest
import os
import sys
import importlib
from unittest.mock import patch
from fastapi.testclient import TestClient

# Add backend directory to path
BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.append(BACKEND_DIR)
os.chdir(BACKEND_DIR)

class TestXSS(unittest.TestCase):
    def setUp(self):
        # Force Development Env
        self.env_patcher = patch.dict(os.environ, {"APP_ENV": "development"})
        self.env_patcher.start()

        # Reload main to ensure it picks up the env
        import main
        importlib.reload(main)
        from main import app

        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer dev-token"}

    def tearDown(self):
        self.env_patcher.stop()

    def test_xss_web_url_blocked(self):
        """Ensure javascript: URLs are blocked for web_url type."""
        with self.client:
            response = self.client.post(
                "/api/share",
                headers=self.headers,
                json={
                    "type": "web_url",
                    "content": "javascript:alert(1)",
                    "title": "Malicious Link"
                }
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn("Invalid URL scheme", response.text)

    def test_xss_data_url_blocked(self):
        """Ensure data: URLs are blocked for web_url type."""
        with self.client:
            response = self.client.post(
                "/api/share",
                headers=self.headers,
                json={
                    "type": "web_url",
                    "content": "data:text/html,<script>alert(1)</script>",
                    "title": "Malicious Data"
                }
            )
            self.assertEqual(response.status_code, 400)
            # This hits the web_url scheme check first
            self.assertIn("Invalid URL scheme", response.text)

    def test_global_xss_block(self):
        """Ensure javascript: content is blocked even for text type."""
        with self.client:
            response = self.client.post(
                "/api/share",
                headers=self.headers,
                json={
                    "type": "text",
                    "content": "javascript:alert(1)",
                    "title": "Malicious Text"
                }
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn("Invalid content", response.text)

if __name__ == '__main__':
    unittest.main()
