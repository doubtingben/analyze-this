import os
import time
from collections import defaultdict
from fastapi import Request, HTTPException

class RateLimiter:
    """
    Simple in-memory rate limiter using a sliding window of timestamps.
    """
    def __init__(self, max_calls: int, time_frame: int):
        self.max_calls = max_calls
        self.time_frame = time_frame
        self.clients = defaultdict(list)

    async def __call__(self, request: Request):
        # Allow disabling rate limit for testing/development if needed
        if os.getenv("NO_RATE_LIMIT", "false").lower() == "true":
            return

        # Get IP address (support X-Forwarded-For for proxies/Cloud Run)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        now = time.time()

        # Filter out timestamps older than the time_frame
        # We assign back to self.clients[client_ip] to keep only relevant timestamps
        self.clients[client_ip] = [
            timestamp for timestamp in self.clients[client_ip]
            if now - timestamp < self.time_frame
        ]

        if len(self.clients[client_ip]) >= self.max_calls:
            raise HTTPException(status_code=429, detail="Too Many Requests")

        self.clients[client_ip].append(now)
