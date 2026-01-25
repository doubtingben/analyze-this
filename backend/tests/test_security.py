import unittest
import os
import sys
from fastapi.testclient import TestClient

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Mock Environment BEFORE importing main
os.environ["APP_ENV"] = "development"

from main import app

class TestSecurity(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.user_email = "dev@example.com"
        self.headers = {"Authorization": "Bearer dev-token"}

        # Ensure directory exists for legit test
        self.backend_dir = os.path.dirname(os.path.dirname(__file__))
        self.test_dir = os.path.join(self.backend_dir, "static", "uploads", self.user_email)
        os.makedirs(self.test_dir, exist_ok=True)
        self.test_file = os.path.join(self.test_dir, "test_security.txt")
        with open(self.test_file, "w") as f:
            f.write("Safe content")

    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
        # Try to remove directory if empty
        try:
            os.rmdir(self.test_dir)
        except OSError:
            pass

    def test_legitimate_access(self):
        """Ensure legitimate files can still be accessed."""
        path = f"uploads/{self.user_email}/test_security.txt"
        response = self.client.get(f"/api/content/{path}", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "Safe content")

    def test_path_traversal_attempt(self):
        """Ensure path traversal is blocked."""
        # Use encoded dots to bypass client normalization
        encoded_dots = "%2E%2E"
        # Path attempting to go up 3 levels to reach main.py
        encoded_path = f"uploads/{self.user_email}/{encoded_dots}/{encoded_dots}/{encoded_dots}/main.py"

        response = self.client.get(f"/api/content/{encoded_path}", headers=self.headers)

        # We expect 403 Forbidden based on our fix
        self.assertEqual(response.status_code, 403)
        self.assertIn("Forbidden", response.text)

    def test_access_other_user_file(self):
        """Ensure user cannot access another user's files via prefix mismatch."""
        other_user = "victim@example.com"
        # Create a file for other user
        other_dir = os.path.join(self.backend_dir, "static", "uploads", other_user)
        os.makedirs(other_dir, exist_ok=True)
        other_file = os.path.join(other_dir, "secret.txt")
        with open(other_file, "w") as f:
            f.write("Secret content")

        try:
            path = f"uploads/{other_user}/secret.txt"
            response = self.client.get(f"/api/content/{path}", headers=self.headers)

            # The code checks expected_prefix = f"uploads/{user_email}/"
            # So this should fail with 403
            self.assertEqual(response.status_code, 403)
        finally:
            if os.path.exists(other_file):
                os.remove(other_file)
            if os.path.exists(other_dir):
                os.rmdir(other_dir)

if __name__ == '__main__':
    unittest.main()
