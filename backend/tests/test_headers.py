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
# We want to test production-like behavior for HSTS if possible,
# but middleware often runs regardless of env. Let's check dev behavior first.
os.environ["APP_ENV"] = "development"

from main import app

class TestHeaders(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_security_headers_presence(self):
        """Ensure critical security headers are present in responses."""
        response = self.client.get("/")

        # CSP
        self.assertIn("content-security-policy", response.headers)
        csp = response.headers["content-security-policy"]
        self.assertIn("default-src 'self'", csp)
        self.assertIn("object-src 'none'", csp)
        self.assertIn("script-src", csp)

        # Permissions Policy
        self.assertIn("permissions-policy", response.headers)
        pp = response.headers["permissions-policy"]
        self.assertIn("camera=()", pp)
        self.assertIn("microphone=()", pp)
        self.assertIn("geolocation=()", pp)

        # Referrer Policy
        self.assertIn("referrer-policy", response.headers)
        self.assertEqual(response.headers["referrer-policy"], "strict-origin-when-cross-origin")

        # HSTS (might be missing in dev, so check conditional logic or if it's always on)
        # Based on typical implementations, it might be dev-disabled.
        # But we check for the others which should be always on.

    def test_csp_script_src(self):
        """Ensure CSP allows necessary script sources but not overly permissive."""
        response = self.client.get("/")
        csp = response.headers.get("content-security-policy", "")

        # Check for google auth domains if needed
        self.assertIn("https://accounts.google.com", csp)

        # Check that we don't allow *
        self.assertNotIn("script-src *", csp)
        self.assertNotIn("default-src *", csp)

if __name__ == '__main__':
    unittest.main()
