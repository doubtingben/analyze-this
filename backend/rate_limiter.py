import time
import os
from collections import defaultdict
from fastapi import Request, HTTPException, status

class RateLimiter:
    """
    Simple in-memory rate limiter using a fixed window strategy.

    Args:
        requests (int): Maximum number of requests allowed in the window.
        window (int): Time window in seconds.
    """
    def __init__(self, requests: int, window: int):
        self.requests = requests
        self.window = window
        self.clients = defaultdict(list)

    async def __call__(self, request: Request):
        # Allow disabling rate limits for testing or special environments
        if os.getenv("NO_RATE_LIMIT"):
            return

        # Identify client by IP address
        client_ip = request.client.host if request.client else "unknown"

        # Memory protection: Clear storage if too many clients are tracked to prevent memory exhaustion
        if len(self.clients) > 10000:
            self.clients.clear()

        now = time.time()

        # Filter out timestamps outside the current window
        # We keep only timestamps that are within the last `window` seconds
        self.clients[client_ip] = [
            t for t in self.clients[client_ip]
            if now - t < self.window
        ]

        # Check if request count exceeds limit
        if len(self.clients[client_ip]) >= self.requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests"
            )

        # Record the current request
        self.clients[client_ip].append(now)
