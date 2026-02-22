import os
from slowapi import Limiter
from starlette.requests import Request

def get_real_user_ip(request: Request):
    """
    Get the real user IP address, respecting X-Forwarded-For header
    which is critical when running behind Cloud Run load balancers.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return (request.client and request.client.host) or "127.0.0.1"

# Check if rate limits should be disabled (e.g. for testing)
enabled = os.getenv("NO_RATE_LIMIT", "").lower() not in ("true", "1", "yes")

# Explicitly use memory storage to avoid ambiguity
# Disable headers to avoid crash with FastAPI return values (dicts/models)
limiter = Limiter(key_func=get_real_user_ip, enabled=enabled, storage_uri="memory://", headers_enabled=False)
