import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from main import app

client = TestClient(app)

@patch("main.db")
def test_error_leakage(mock_db):
    mock_db.create_item_note.side_effect = Exception("SuperSecretDatabaseError")

    # Try uploading note, forcing an error
    response = client.post("/api/items/test-item/notes", data={"text": "Hello"})

    # In development mode, details are leaked (but maybe we should handle 500 error globally with an exception handler)
    print(response.status_code)
    print(response.text)

test_error_leakage()
