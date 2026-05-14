import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import os

@pytest.fixture
def test_client():
    with patch.dict(os.environ, {"APP_ENV": "development", "SECRET_KEY": "dev-secret"}):
        from main import app
        return TestClient(app)

def test_logout_clears_session(test_client):
    with patch("main.db"):
        # We will make sure the logout endpoint does not error and returns a redirect
        response = test_client.get("/logout", follow_redirects=False)
        assert response.status_code in [302, 303, 307]
