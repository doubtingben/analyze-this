
import asyncio
import unittest
from unittest.mock import patch
import sys
import os
import shutil

# Add backend directory to path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(BACKEND_DIR)
os.chdir(BACKEND_DIR)

# Ensure development mode
os.environ["APP_ENV"] = "development"

import database
import main
from fastapi.testclient import TestClient

class TestImageFieldIntegration(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_url = f"sqlite+aiosqlite:///{self.temp_dir.name}/test_api_image.db"
        
        # Patch the SQLiteDatabase class in main to ensuring it uses our test DB URL if main creates new instances
        # But crucially, we also manually set main.db to our test DB instance
        self.db_patcher = patch("main.SQLiteDatabase", lambda: database.SQLiteDatabase(self.db_url))
        self.db_patcher.start()
        
        # Initialize the database
        main.db = database.SQLiteDatabase(self.db_url)
        asyncio.run(main.db.init_db())
        
        # Override the dependency if necessary, but main.app uses main.db global
        self.client = TestClient(main.app)
        self.headers = {"Authorization": "Bearer dev-token"}

    def tearDown(self):
        self.db_patcher.stop()
        asyncio.run(main.db.close())
        self.temp_dir.cleanup()

    def test_create_image_populates_image_field(self):
        # We need to simulate a file upload or just form data. 
        # The endpoint handles multipart/form-data.
        # But if we want to test the logic 'normalize_share_type' and subsequent populating,
        # we can just send the JSON payload if we were using the extension logic?
        # main.py line 419: if 'application/json' in content_type:
        
        payload = {"title": "My Image", "content": "uploads/dev@example.com/img.png", "type": "image"}
        response = self.client.post("/api/share", json=payload, headers=self.headers)
        
        print(f"Response: {response.text}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["type"], "image")
        self.assertEqual(data["image"], "uploads/dev@example.com/img.png")

    def test_create_screenshot_populates_image_field(self):
        payload = {"title": "My Screenshot", "content": "uploads/dev@example.com/screen.png", "type": "screenshot"}
        response = self.client.post("/api/share", json=payload, headers=self.headers)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["type"], "screenshot")
        self.assertEqual(data["image"], "uploads/dev@example.com/screen.png")

    def test_create_text_does_not_populate_image_field(self):
        payload = {"title": "My Text", "content": "Hello World", "type": "text"}
        response = self.client.post("/api/share", json=payload, headers=self.headers)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["type"], "text")
        self.assertIsNone(data["image"])

if __name__ == "__main__":
    unittest.main()
