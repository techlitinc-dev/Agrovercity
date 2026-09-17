import logging
import time

from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core import cache

logger = logging.getLogger(__name__)

SKIP_PATHS = {"/v1/health", "/docs", "/openapi.json", "/redoc"}
RATE_LIMIT = 100


def _identity(request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        try:
            from jose import jwt

            claims = jwt.decode(auth.split(" ", 1)[1], options={"verify_signature": False})
            sub = claims.get("sub")
            if sub:
                return f"u:{sub}"
        except Exception:
            pass
    client = request.client
    return f"ip:{client.host if client else 'unknown'}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        identity = _identity(request)
        minute_bucket = int(time.time() // 60)
        key = f"rl:{identity}:{minute_bucket}"
        try:
            redis = await cache.get_redis()
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, 70)
            if count > RATE_LIMIT:
                retry_after = max(1, 60 - int(time.time() % 60))
                return JSONResponse(
                    status_code=429,
                    content={"error": {"code": "RATE_LIMITED", "message": "Too many requests", "fieldErrors": {}}},
                    headers={"Retry-After": str(retry_after)},
                )
        except Exception:
            # fail open — Redis outage must not take the API down
            logger.warning("Rate limiter unavailable — failing open", exc_info=True)
        return await call_next(request)
