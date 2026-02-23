from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from starlette.requests import Request

def get_real_user_ip(request: Request) -> str:
    """
    Get IP address from X-Forwarded-For header (common in proxies/Cloud Run)
    or fall back to the direct client host.
    """
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        # The first IP in the list is the original client
        return x_forwarded_for.split(",")[0].strip()
    # request.client can be None in test clients sometimes
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"

# Initialize Limiter with in-memory storage
# headers_enabled=False prevents crashes when endpoints return Pydantic models
limiter = Limiter(key_func=get_real_user_ip, headers_enabled=False)
