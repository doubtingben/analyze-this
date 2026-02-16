import time
from typing import Dict, Tuple
from fastapi import Request, HTTPException, status

class RateLimiter:
    """
    Simple in-memory rate limiter using a fixed window counter.
    """
    def __init__(self):
        # Storage format: {client_ip: {key: (count, reset_time)}}
        self._limits: Dict[str, Dict[str, Tuple[int, float]]] = {}

    def is_allowed(self, client_ip: str, key: str, limit: int, window: int) -> bool:
        now = time.time()

        # Simple cleanup to prevent OOM
        if len(self._limits) > 10000:
            self._limits.clear()

        if client_ip not in self._limits:
            self._limits[client_ip] = {}

        if key not in self._limits[client_ip]:
            self._limits[client_ip][key] = (1, now + window)
            return True

        count, reset_time = self._limits[client_ip][key]

        if now > reset_time:
            # Window expired, reset
            self._limits[client_ip][key] = (1, now + window)
            return True

        if count < limit:
            # Increment count
            self._limits[client_ip][key] = (count + 1, reset_time)
            return True

        return False

    def reset(self):
        """Reset all limits (useful for testing)"""
        self._limits.clear()

# Global instance
limiter = RateLimiter()

def get_remote_address(request: Request) -> str:
    """
    Get client IP address, respecting X-Forwarded-For header.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

class RateLimit:
    """
    FastAPI dependency for rate limiting.
    Usage: dependencies=[Depends(RateLimit(limit=5, window=60, scope="login"))]
    """
    def __init__(self, limit: int, window: int = 60, scope: str = "default"):
        self.limit = limit
        self.window = window
        self.scope = scope

    async def __call__(self, request: Request):
        client_ip = get_remote_address(request)
        # Key is combination of scope
        key = self.scope

        if not limiter.is_allowed(client_ip, key, self.limit, self.window):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests"
            )
