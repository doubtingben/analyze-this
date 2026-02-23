import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

# Set environment to development to avoid Firebase/GCP init
os.environ["APP_ENV"] = "development"
os.environ["NO_RATE_LIMIT"] = "false"

# Import app after setting env
from main import app

client = TestClient(app)

def test_login_rate_limit():
    """Test that login endpoint is rate limited to 5/minute"""
    # Use a unique IP for this test
    headers = {"X-Forwarded-For": "10.0.0.1"}

    # Consume the limit (5 requests)
    for i in range(5):
        response = client.get("/login", headers=headers, follow_redirects=False)
        # Login redirects to Google or returns 200/302/307
        assert response.status_code != 429, f"Request {i+1} failed with 429"

    # The 6th request should fail
    response = client.get("/login", headers=headers, follow_redirects=False)
    assert response.status_code == 429
    assert "Rate limit exceeded" in response.text

def test_share_rate_limit():
    """Test that share endpoint is rate limited to 20/minute"""
    headers = {"X-Forwarded-For": "10.0.0.2", "Authorization": "Bearer test-token"}

    # Mock verify_google_token so we pass the manual auth check inside share_item
    with patch("main.verify_google_token") as mock_verify:
        mock_verify.return_value = {"email": "test@example.com"}

        # Consume the limit (20 requests)
        for i in range(20):
            # Sending minimal data to reach the function body
            # We don't care if it fails logic, as long as it reaches the rate limiter
            response = client.post(
                "/api/share",
                headers=headers,
                data={"title": "test"},
                follow_redirects=False
            )
            assert response.status_code != 429, f"Request {i+1} failed with 429"

        # The 21st request should fail
        response = client.post(
            "/api/share",
            headers=headers,
            data={"title": "test"},
            follow_redirects=False
        )
        assert response.status_code == 429

def test_search_rate_limit():
    """Test that search endpoint is rate limited to 20/minute"""
    headers = {"X-Forwarded-For": "10.0.0.3", "Authorization": "Bearer test-token"}

    with patch("main.verify_google_token") as mock_verify, \
         patch("database.SQLiteDatabase.search_similar_items") as mock_search, \
         patch("main.generate_embedding") as mock_embed:

        mock_verify.return_value = {"email": "test@example.com"}
        mock_search.return_value = []
        mock_embed.return_value = [0.1, 0.2]

        for i in range(20):
            response = client.get("/api/search?q=test", headers=headers)
            assert response.status_code != 429, f"Request {i+1} failed with 429"

        response = client.get("/api/search?q=test", headers=headers)
        assert response.status_code == 429

def test_ip_isolation():
    """Verify that limits are per-IP"""
    headers_a = {"X-Forwarded-For": "10.0.0.4"}
    headers_b = {"X-Forwarded-For": "10.0.0.5"}

    # Exhaust IP A
    for _ in range(5):
        client.get("/login", headers=headers_a, follow_redirects=False)

    assert client.get("/login", headers=headers_a, follow_redirects=False).status_code == 429

    # IP B should still be allowed
    assert client.get("/login", headers=headers_b, follow_redirects=False).status_code != 429

def test_x_forwarded_for_parsing():
    """Verify that we use the first IP in X-Forwarded-For"""
    # 10.0.0.6 is the real client, 1.2.3.4 is a proxy
    headers = {"X-Forwarded-For": "10.0.0.6, 1.2.3.4"}

    for _ in range(5):
        client.get("/login", headers=headers, follow_redirects=False)

    assert client.get("/login", headers=headers, follow_redirects=False).status_code == 429

    # A request from 1.2.3.4 (the proxy IP) as the client IP should still be allowed
    # if we correctly identified 10.0.0.6 as the culprit.
    # But wait, if we send X-Forwarded-For: 1.2.3.4, it treats it as 1.2.3.4.

    headers_proxy = {"X-Forwarded-For": "1.2.3.4"}
    assert client.get("/login", headers=headers_proxy, follow_redirects=False).status_code != 429
