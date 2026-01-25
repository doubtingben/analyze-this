import asyncio
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

# Add backend directory to path
BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.append(BACKEND_DIR)
os.chdir(BACKEND_DIR)

import database

# Ensure development mode for auth + SQLite usage
os.environ["APP_ENV"] = "development"

import main


class TestApi(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_url = f"sqlite+aiosqlite:///{self.temp_dir.name}/test_api.db"
        self.db_patcher = patch("main.SQLiteDatabase", lambda: database.SQLiteDatabase(self.db_url))
        self.db_patcher.start()
        main.db = database.SQLiteDatabase(self.db_url)
        asyncio.run(main.db.init_db())
        self.client = TestClient(main.app)
        self.headers = {"Authorization": "Bearer dev-token"}

    def tearDown(self):
        self.db_patcher.stop()
        self.temp_dir.cleanup()

    def test_share_requires_auth(self):
        response = self.client.post("/api/share", json={"title": "Hi"})
        self.assertEqual(response.status_code, 401)

    def test_share_json_success_and_list_items(self):
        payload = {"title": "Hello", "content": "World", "type": "text"}
        response = self.client.post("/api/share", json=payload, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Hello")

        items_response = self.client.get("/api/items", headers=self.headers)
        self.assertEqual(items_response.status_code, 200)
        items = items_response.json()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["content"], "World")

    def test_share_rejects_unsupported_content_type(self):
        response = self.client.post(
            "/api/share",
            data="plain text",
            headers={"Authorization": "Bearer dev-token", "content-type": "text/plain"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Unsupported Content-Type")

    def test_items_requires_auth(self):
        response = self.client.get("/api/items")
        self.assertEqual(response.status_code, 401)

    def test_delete_missing_item_returns_404(self):
        response = self.client.delete("/api/items/does-not-exist", headers=self.headers)
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
