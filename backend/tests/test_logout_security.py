import pytest
import sys
import os
from unittest.mock import patch
import asyncio

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

@pytest.fixture(autouse=True)
def mock_env():
    with patch.dict(os.environ, {"APP_ENV": "development"}):
        yield

from fastapi.testclient import TestClient
from fastapi import Request

@pytest.mark.anyio
async def test_logout_clears_entire_session():
    # Delay import so mock_env takes effect
    from main import logout

    # Create a mock request with a populated session
    class MockRequest:
        def __init__(self):
            self.session = {
                "user": {"email": "test@example.com"},
                "csrf_token": "secret123",
                "other_data": "value"
            }

    mock_req = MockRequest()

    # Call the logout endpoint handler directly
    response = await logout(mock_req)

    # Assert session is empty
    assert len(mock_req.session) == 0, f"Session should be empty, but was {mock_req.session}"
    assert response.status_code == 307  # RedirectResponse default status code
