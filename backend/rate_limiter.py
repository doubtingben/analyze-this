import os
import time
from collections import defaultdict, deque
from fastapi import Request, HTTPException, status

class RateLimiter:
    """
    Simple in-memory sliding window rate limiter.
    """
    def __init__(self, times: int, seconds: int):
        self.times = times
        self.seconds = seconds
        self.history = defaultdict(deque)
        self.last_cleanup = time.time()
        # Allow disabling rate limiting for testing/dev via env var
        self.enabled = os.getenv("NO_RATE_LIMIT", "0") != "1"

    async def __call__(self, request: Request):
        if not self.enabled:
            return

        ip = "unknown"
        if request.client and request.client.host:
            ip = request.client.host

        # Support X-Forwarded-For if behind a proxy (e.g. Cloud Run)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()

        now = time.time()

        # Periodic cleanup (every 10x window or 60s)
        if now - self.last_cleanup > max(60, self.seconds * 10):
            self.cleanup(now)
            self.last_cleanup = now

        # Check limit
        history = self.history[ip]
        while history and history[0] < now - self.seconds:
            history.popleft()

        if len(history) >= self.times:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests"
            )

        history.append(now)

    def cleanup(self, now):
        """Remove expired entries to prevent memory leaks."""
        for ip in list(self.history.keys()):
            dq = self.history[ip]
            while dq and dq[0] < now - self.seconds:
                dq.popleft()
            if not dq:
                del self.history[ip]
