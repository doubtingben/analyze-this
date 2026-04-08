import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from main import app
import os

client = TestClient(app)

@patch("main.db")
@patch("main.verify_google_token")
def test_error_leakage(mock_verify, mock_db):
    mock_verify.return_value = {"email": "test@example.com"}

    mock_db.get_shared_item = AsyncMock(return_value={"user_email": "test@example.com", "id": "test-item"})
    mock_db.create_item_note = AsyncMock()

    # Force upload error
    with patch("main.shutil.copyfileobj", side_effect=Exception("SuperSecretDatabaseError")):
        # Mock file
        from io import BytesIO
        file = {"file": ("test.txt", BytesIO(b"test"), "text/plain")}

        response = client.post("/api/items/test-item/notes", data={"note_type": "context"}, files=file, headers={"Authorization": "Bearer token"})

        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")

test_error_leakage()
