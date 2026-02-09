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

class TestUploadSecurity(unittest.TestCase):
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

    @patch('shutil.copyfileobj') # Mock file writing to avoid disk I/O
    def test_upload_html_file_xss(self, mock_copy):
        """
        Test that uploading a file with text/html content type is REJECTED.
        """
        files = {
            'file': ('exploit.html', '<script>alert(1)</script>', 'text/html')
        }
        data = {
            'type': 'file'
        }

        with self.client as client:
            response = client.post(
                "/api/share",
                headers=self.headers,
                data=data,
                files=files
            )

            self.assertEqual(response.status_code, 400, f"Expected 400 Bad Request for text/html upload, got {response.status_code}")
            self.assertIn("Unsupported file type", response.text)

    @patch('shutil.copyfileobj')
    def test_upload_html_as_image(self, mock_copy):
        """
        Test that uploading an HTML file with image/png content type is REJECTED
        due to extension check.
        """
        files = {
            'file': ('exploit.html', '<script>alert(1)</script>', 'image/png')
        }
        data = {
            'type': 'file'
        }

        with self.client as client:
            response = client.post(
                "/api/share",
                headers=self.headers,
                data=data,
                files=files
            )

            self.assertEqual(response.status_code, 400, f"Expected 400 Bad Request for HTML extension, got {response.status_code}")
            self.assertIn("Unsupported file extension", response.text)

    @patch('shutil.copyfileobj')
    def test_upload_valid_file(self, mock_copy):
        """
        Test that uploading a file with a valid content type (text/plain) is ACCEPTED.
        """
        files = {
            'file': ('safe.txt', 'Hello World', 'text/plain')
        }
        data = {
            'type': 'file'
        }

        with self.client as client:
            response = client.post(
                "/api/share",
                headers=self.headers,
                data=data,
                files=files
            )

            self.assertEqual(response.status_code, 200, f"Expected 200 OK for text/plain upload, got {response.status_code}. Details: {response.text}")
            json_resp = response.json()
            self.assertEqual(json_resp['type'], 'file')

    def test_security_headers(self):
        """
        Test that security headers (X-Content-Type-Options, X-Frame-Options) are present.
        """
        with self.client as client:
            response = client.get("/")

            self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
            self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")

if __name__ == '__main__':
    unittest.main()
