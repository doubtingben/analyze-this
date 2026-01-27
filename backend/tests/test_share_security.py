import unittest
import os
import sys
from fastapi.testclient import TestClient

# Add backend directory to path
BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)
os.chdir(BACKEND_DIR)

# Mock Environment BEFORE importing main
os.environ["APP_ENV"] = "development"

from main import app

class TestShareSecurity(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.client.__enter__()
        self.user_email = "dev@example.com"
        # We use the dev-token which makes verify_google_token return dev@example.com
        self.headers = {"Authorization": "Bearer dev-token", "Content-Type": "application/json"}

    def tearDown(self):
        self.client.__exit__(None, None, None)

    def test_share_malicious_content_path(self):
        """Ensure user cannot create a shared item with content path pointing to another user's file."""
        malicious_path = "uploads/victim@example.com/secret.png"
        payload = {
            "title": "Malicious Item",
            "type": "image",
            "content": malicious_path
        }

        response = self.client.post("/api/share", json=payload, headers=self.headers)

        # We expect 403 Forbidden
        self.assertEqual(response.status_code, 403, f"Should return 403 but got {response.status_code}")

    def test_share_path_traversal(self):
        """Ensure user cannot use path traversal in content."""
        malicious_path = f"uploads/{self.user_email}/../../secret.png"
        payload = {
            "title": "Traversal Item",
            "type": "image",
            "content": malicious_path
        }

        response = self.client.post("/api/share", json=payload, headers=self.headers)
        self.assertEqual(response.status_code, 403, f"Should return 403 but got {response.status_code}")

    def test_legitimate_url(self):
        """Ensure legitimate URLs are still allowed."""
        payload = {
            "title": "Valid URL",
            "type": "web_url",
            "content": "https://example.com/image.png"
        }
        response = self.client.post("/api/share", json=payload, headers=self.headers)
        self.assertEqual(response.status_code, 200)

    def test_legitimate_upload_path(self):
        """Ensure legitimate upload paths are still allowed."""
        valid_path = f"uploads/{self.user_email}/somefile.png"
        payload = {
            "title": "Valid File",
            "type": "image",
            "content": valid_path
        }
        response = self.client.post("/api/share", json=payload, headers=self.headers)
        self.assertEqual(response.status_code, 200)

if __name__ == '__main__':
    unittest.main()
