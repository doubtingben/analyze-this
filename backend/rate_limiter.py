import time
import os
from collections import defaultdict, deque
from typing import Dict, Deque

class RateLimiter:
    """
    A simple in-memory rate limiter using a sliding window log algorithm.
    """
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, Deque[float]] = defaultdict(deque)

        # Check if rate limiting is disabled via environment variable (for testing)
        self.disabled = os.getenv("NO_RATE_LIMIT", "").lower() in ("true", "1", "yes")

    def is_allowed(self, client_id: str) -> bool:
        """
        Check if the client is allowed to make a request.
        Returns True if allowed, False if limit exceeded.
        """
        if self.disabled:
            return True

        now = time.time()
        queue = self.requests[client_id]

        # Remove timestamps outside the window
        while queue and queue[0] < now - self.window_seconds:
            queue.popleft()

        # Check if limit exceeded
        if len(queue) >= self.max_requests:
            return False

        # Record current request
        queue.append(now)

        # Memory protection: Clear all if too many clients are tracked
        # This prevents memory exhaustion attacks
        if len(self.requests) > 10000:
            self.requests.clear()
            # Re-add current client so they aren't penalized immediately after clear,
            # though strictly speaking they just got a free pass.
            # Ideally we'd keep them, but clearing all is safer for memory.
            self.requests[client_id].append(now)

        return True
