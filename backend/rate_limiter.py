import time
from collections import defaultdict, deque
from fastapi import Request, HTTPException, status
from typing import Optional

class RateLimiter:
    """
    A simple fixed-window rate limiter using deque.
    """
    def __init__(self, requests: int, window: int):
        self.requests = requests
        self.window = window
        self.clients = defaultdict(deque)
        self.last_cleanup = time.time()

    def is_allowed(self, client_id: str) -> bool:
        now = time.time()

        # Cleanup periodically (every 60s or if too many clients)
        if now - self.last_cleanup > 60:
            self.cleanup(now)
            self.last_cleanup = now

        timestamps = self.clients[client_id]

        # Remove old timestamps
        while timestamps and timestamps[0] <= now - self.window:
            timestamps.popleft()

        if len(timestamps) >= self.requests:
            return False

        timestamps.append(now)
        return True

    def cleanup(self, now: float):
        # Remove empty clients and old timestamps
        cutoff = now - self.window
        for client_id in list(self.clients.keys()):
            timestamps = self.clients[client_id]
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if not timestamps:
                del self.clients[client_id]

        # Memory protection: Clear all if too many clients to prevent DoS
        if len(self.clients) > 10000:
            self.clients.clear()

class RateLimit:
    """
    FastAPI dependency for rate limiting.
    """
    def __init__(self, requests: int = 10, window: int = 60):
        self.limiter = RateLimiter(requests, window)

    async def __call__(self, request: Request):
        client_ip = self.get_client_ip(request)
        if not self.limiter.is_allowed(client_ip):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later."
            )

    def get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
