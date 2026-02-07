import unittest
import os
import sys
from fastapi.testclient import TestClient

# Add backend directory to path
BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.append(BACKEND_DIR)
os.chdir(BACKEND_DIR)

# Mock Environment
os.environ["APP_ENV"] = "development"

from main import app

class TestSecurityHeaders(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_security_headers_present(self):
        """Ensure security headers are set on responses."""
        response = self.client.get("/")

        # Check for Security Headers
        self.assertIn("X-Content-Type-Options", response.headers)
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

        self.assertIn("X-Frame-Options", response.headers)
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")

        self.assertIn("Content-Security-Policy", response.headers)
        # Basic check for CSP presence and key directives
        csp = response.headers["Content-Security-Policy"]
        self.assertIn("default-src 'self'", csp)
        self.assertIn("script-src", csp)

        self.assertIn("Referrer-Policy", response.headers)
        self.assertEqual(response.headers["Referrer-Policy"], "strict-origin-when-cross-origin")

if __name__ == '__main__':
    unittest.main()
