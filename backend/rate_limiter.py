import time
import os
from collections import deque
from fastapi import Request, HTTPException

class RateLimiter:
    """
    A simple in-memory rate limiter using a fixed window algorithm.
    """
    def __init__(self, requests_limit: int, time_window: int):
        self.requests_limit = requests_limit
        self.time_window = time_window
        self.clients = {}

    async def __call__(self, request: Request):
        # Allow disabling for testing
        if os.getenv("NO_RATE_LIMIT"):
            return

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        # Memory protection: Clear storage if too many clients are tracked
        if len(self.clients) > 10000:
            self.clients.clear()

        if client_ip not in self.clients:
            self.clients[client_ip] = deque()

        request_times = self.clients[client_ip]

        # Remove timestamps outside the window
        while request_times and now - request_times[0] > self.time_window:
            request_times.popleft()

        if len(request_times) >= self.requests_limit:
            raise HTTPException(status_code=429, detail="Too Many Requests")

        request_times.append(now)
