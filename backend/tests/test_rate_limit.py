import os
import time
import pytest
from unittest.mock import patch, MagicMock
from fastapi import Request, HTTPException, status

# Set environment before imports
os.environ["APP_ENV"] = "development"
os.environ["SECRET_KEY"] = "test-secret"

from rate_limiter import RateLimiter, RateLimit

# --- Unit Tests for RateLimiter Class ---

def test_rate_limiter_allow():
    limiter = RateLimiter(requests=2, window=1)
    assert limiter.is_allowed("user1") is True
    assert limiter.is_allowed("user1") is True
    assert limiter.is_allowed("user1") is False

def test_rate_limiter_window_reset():
    with patch("rate_limiter.time.time") as mock_time:
        start_time = 1000.0
        mock_time.return_value = start_time
        limiter = RateLimiter(requests=1, window=10)

        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user1") is False

        # Advance time beyond window
        mock_time.return_value = start_time + 11.0
        assert limiter.is_allowed("user1") is True

def test_rate_limiter_cleanup():
    with patch("rate_limiter.time.time") as mock_time:
        start_time = 1000.0
        mock_time.return_value = start_time
        limiter = RateLimiter(requests=10, window=10)

        limiter.is_allowed("user1")
        assert "user1" in limiter.clients

        # Advance time significantly to trigger cleanup (cleanup runs if > 60s passed)
        mock_time.return_value = start_time + 70.0

        # Trigger cleanup
        limiter.is_allowed("user2")

        # user1 should be gone as its timestamps are old
        assert "user1" not in limiter.clients

def test_rate_limiter_dos_protection():
    limiter = RateLimiter(requests=10, window=60)
    # Manually populate clients
    for i in range(10001):
        limiter.clients[f"user{i}"].append(time.time())

    assert len(limiter.clients) > 10000

    # Trigger cleanup via is_allowed
    # The logic checks if now - last_cleanup > 60.
    limiter.last_cleanup = time.time() - 61

    limiter.is_allowed("new_user")

    # Should have cleared
    assert len(limiter.clients) <= 1

# --- Integration Tests with RateLimit Dependency ---

@pytest.mark.asyncio
async def test_rate_limit_dependency():
    rate_limit = RateLimit(requests=2, window=60)

    request = MagicMock(spec=Request)
    request.client.host = "127.0.0.1"
    request.headers.get.return_value = None # No forwarded for

    # Should pass
    await rate_limit(request)
    await rate_limit(request)

    # Should fail
    with pytest.raises(HTTPException) as excinfo:
        await rate_limit(request)

    assert excinfo.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS

@pytest.mark.asyncio
async def test_rate_limit_x_forwarded_for():
    rate_limit = RateLimit(requests=1, window=60)

    request = MagicMock(spec=Request)
    request.client.host = "proxy-ip"
    request.headers.get.return_value = "real-ip, other-ip"

    # Should pass for real-ip
    await rate_limit(request)

    # Should fail for real-ip
    with pytest.raises(HTTPException):
        await rate_limit(request)

    # Should pass for different ip
    request.headers.get.return_value = "another-ip"
    await rate_limit(request)
