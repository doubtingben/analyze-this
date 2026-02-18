import os
import time
from collections import deque
from fastapi import Request, HTTPException, status

class RateLimiter:
    """
    Simple in-memory rate limiter using a sliding window algorithm.
    """
    def __init__(self, limit: int, window_seconds: int = 60):
        self.limit = limit
        self.window_seconds = window_seconds
        self.requests = {}
        # Environment variable to bypass rate limits (useful for testing)
        self.no_rate_limit = os.getenv("NO_RATE_LIMIT", "").lower() in ("true", "1", "yes")

    def is_allowed(self, key: str) -> bool:
        if self.no_rate_limit:
            return True

        # Memory protection: clear if too many keys to prevent memory exhaustion
        if len(self.requests) > 10000:
            self.requests.clear()

        now = time.time()
        if key not in self.requests:
            self.requests[key] = deque()

        queue = self.requests[key]

        # Remove old requests outside the window
        while queue and now - queue[0] > self.window_seconds:
            queue.popleft()

        # Check limit
        if len(queue) >= self.limit:
            return False

        # Record new request
        queue.append(now)
        return True

# Global limiters
# Login: 10 requests per minute
login_limiter = RateLimiter(limit=10, window_seconds=60)

# Share: 20 requests per minute (file uploads are resource intensive)
share_limiter = RateLimiter(limit=20, window_seconds=60)

# Search: 20 requests per minute (embedding generation is costly)
search_limiter = RateLimiter(limit=20, window_seconds=60)

# Notes: 20 requests per minute
note_limiter = RateLimiter(limit=20, window_seconds=60)

async def check_login_rate_limit(request: Request):
    key = request.client.host if request.client else "unknown"
    if not login_limiter.is_allowed(key):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too Many Requests")

async def check_share_rate_limit(request: Request):
    key = request.client.host if request.client else "unknown"
    if not share_limiter.is_allowed(key):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too Many Requests")

async def check_search_rate_limit(request: Request):
    key = request.client.host if request.client else "unknown"
    if not search_limiter.is_allowed(key):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too Many Requests")

async def check_note_rate_limit(request: Request):
    key = request.client.host if request.client else "unknown"
    if not note_limiter.is_allowed(key):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too Many Requests")
