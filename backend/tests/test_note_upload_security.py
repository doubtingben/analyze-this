import unittest
import os
import sys
import importlib
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from datetime import datetime

# Add backend directory to path
BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.append(BACKEND_DIR)
os.chdir(BACKEND_DIR)

# Mock firebase_admin before importing main
if "firebase_admin" not in sys.modules:
    sys.modules["firebase_admin"] = MagicMock()
if "firebase_admin.credentials" not in sys.modules:
    sys.modules["firebase_admin.credentials"] = MagicMock()
if "firebase_admin.storage" not in sys.modules:
    sys.modules["firebase_admin.storage"] = MagicMock()
if "google.cloud.firestore" not in sys.modules:
    sys.modules["google.cloud.firestore"] = MagicMock()

class TestNoteUploadSecurity(unittest.TestCase):
    def setUp(self):
        # Force Development Env
        self.env_patcher = patch.dict(os.environ, {"APP_ENV": "development"})
        self.env_patcher.start()

        # Reload main to ensure it picks up the env
        import main
        importlib.reload(main)
        from main import app

        # Mock the DB interface
        self.mock_db = MagicMock()
        self.mock_db.get_shared_item = AsyncMock(return_value={
            'firestore_id': 'test-item-id',
            'user_email': 'dev@example.com',
            'type': 'text'
        })
        self.mock_db.create_item_note = AsyncMock(return_value=MagicMock(
            id='test-note-id',
            item_id='test-item-id',
            user_email='dev@example.com',
            text='test',
            image_path='uploads/dev@example.com/notes/test.jpg',
            note_type='context',
            created_at=datetime.now(),
            updated_at=datetime.now()
        ))

        main.db = self.mock_db

        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer dev-token"}
        self.item_id = 'test-item-id'

    def tearDown(self):
        self.env_patcher.stop()

    @patch('shutil.copyfileobj')
    def test_upload_html_rejected(self, mock_copy):
        """
        Test that uploading an HTML file is rejected.
        """
        files = {
            'file': ('exploit.html', '<script>alert(1)</script>', 'text/html')
        }
        data = {'note_type': 'context'}

        response = self.client.post(
            f"/api/items/{self.item_id}/notes",
            headers=self.headers,
            data=data,
            files=files
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported file type", response.json()['detail'])

    @patch('shutil.copyfileobj')
    def test_upload_exe_rejected(self, mock_copy):
        """
        Test that uploading an EXE file is rejected.
        """
        files = {
            'file': ('malware.exe', 'MZ...', 'application/x-msdownload')
        }
        data = {'note_type': 'context'}

        response = self.client.post(
            f"/api/items/{self.item_id}/notes",
            headers=self.headers,
            data=data,
            files=files
        )

        self.assertEqual(response.status_code, 400)
        # Could be "Unsupported file type" or "Unsupported file extension" depending on order
        self.assertTrue(
            "Unsupported file type" in response.json()['detail'] or
            "Unsupported file extension" in response.json()['detail']
        )

    @patch('shutil.copyfileobj')
    def test_upload_spoofed_extension_rejected(self, mock_copy):
        """
        Test that uploading an HTML file with .jpg extension is rejected if content-type is wrong.
        Wait, if content-type is image/jpeg but content is HTML?
        The backend only checks content-type header provided by client, not magic bytes (yet).
        But if content-type is text/html and extension is .jpg -> Rejected by content-type.
        If content-type is image/jpeg and extension is .html -> Rejected by extension.
        """
        # Case 1: Bad extension, Good mime (should fail extension check)
        files = {
            'file': ('exploit.html', 'content', 'image/jpeg')
        }
        response = self.client.post(
            f"/api/items/{self.item_id}/notes",
            headers=self.headers,
            data={'note_type': 'context'},
            files=files
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported file extension", response.json()['detail'])

        # Case 2: Good extension, Bad mime (should fail mime check)
        files = {
            'file': ('image.jpg', 'content', 'text/html')
        }
        response = self.client.post(
            f"/api/items/{self.item_id}/notes",
            headers=self.headers,
            data={'note_type': 'context'},
            files=files
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported file type", response.json()['detail'])

    @patch('shutil.copyfileobj')
    def test_upload_valid_image_accepted(self, mock_copy):
        """
        Test that uploading a valid image file is accepted.
        """
        files = {
            'file': ('photo.jpg', 'fake-image-content', 'image/jpeg')
        }
        data = {'note_type': 'context'}

        response = self.client.post(
            f"/api/items/{self.item_id}/notes",
            headers=self.headers,
            data=data,
            files=files
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("id", response.json())

if __name__ == '__main__':
    unittest.main()
