import asyncio
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

# Add backend directory to path
BACKEND_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
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
        asyncio.run(main.db.close())
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

    def test_list_items_with_analysis_structure(self):
        # Create item with new analysis structure
        from models import SharedItem, AnalysisResult, TimelineEvent, ShareType

        analysis = AnalysisResult(
            overview="Test Overview",
            timeline=TimelineEvent(date="2023-01-01", principal="Me"),
            tags=["tag1"]
        )

        item = SharedItem(
            user_email="dev@example.com",
            type=ShareType.text,
            content="Test content",
            analysis=analysis,
            status="timeline"
        )

        asyncio.run(main.db.create_shared_item(item))

        items_response = self.client.get("/api/items", headers=self.headers)
        self.assertEqual(items_response.status_code, 200)
        items = items_response.json()

        # Verify the item with analysis is present
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["analysis"]["overview"], "Test Overview")
        self.assertEqual(items[0]["analysis"]["timeline"]["date"], "2023-01-01")

    def test_export_includes_items_and_files(self):
        from models import SharedItem, ShareType

        uploads_dir = Path("static/uploads/dev@example.com")
        uploads_dir.mkdir(parents=True, exist_ok=True)
        file_path = uploads_dir / "export-test.txt"
        file_bytes = b"exported file contents"
        file_path.write_bytes(file_bytes)

        file_item = SharedItem(
            user_email="dev@example.com",
            type=ShareType.file,
            content="uploads/dev@example.com/export-test.txt",
            title="Export File",
            hidden=True,
        )
        text_item = SharedItem(
            user_email="dev@example.com",
            type=ShareType.text,
            content="Hello export",
            title="Export Text",
        )

        asyncio.run(main.db.create_shared_item(file_item))
        asyncio.run(main.db.create_shared_item(text_item))

        response = self.client.get("/api/export", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("application/zip"))

        with zipfile.ZipFile(io.BytesIO(response.content)) as zipf:
            self.assertIn("items.json", zipf.namelist())
            self.assertIn("export_manifest.json", zipf.namelist())

            items = json.loads(zipf.read("items.json"))
            self.assertEqual(len(items), 2)
            self.assertTrue(any(item.get("hidden") for item in items))

            file_item_export = next(
                item for item in items if item.get("content") == "uploads/dev@example.com/export-test.txt"
            )
            export_path = file_item_export.get("export_file")
            self.assertIsNotNone(export_path)
            self.assertEqual(zipf.read(export_path), file_bytes)

            manifest = json.loads(zipf.read("export_manifest.json"))
            self.assertEqual(manifest["item_count"], 2)
            self.assertTrue(any(entry["export_path"] == export_path for entry in manifest["files"]))

        file_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
