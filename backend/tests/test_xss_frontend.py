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

class TestFrontendXSS(unittest.TestCase):
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

    def test_frontend_js_has_escapeHtml_for_error_message(self):
        """Ensure frontend javascript uses escapeHtml for error messages assigned to innerHTML."""
        js_file = os.path.join(BACKEND_DIR, "static", "app.js")
        with open(js_file, "r") as f:
            content = f.read()
        self.assertIn("escapeHtml(error.message", content)
        self.assertNotIn('detailNotesList.innerHTML = `<div class="detail-muted">${error.message', content)

if __name__ == '__main__':
    unittest.main()
