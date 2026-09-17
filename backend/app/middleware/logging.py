import logging
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware

# Request/response bodies are NEVER logged — Aadhaar numbers and photos pass through this API.
api_logger = logging.getLogger("api")
api_logger.setLevel(logging.INFO)
_handler = logging.StreamHandler()
try:
    from pythonjsonlogger import jsonlogger

    _handler.setFormatter(
        jsonlogger.JsonFormatter("%(ts)s %(method)s %(path)s %(status)s %(durationMs)s %(uid)s %(requestId)s")
    )
except ImportError:
    pass
api_logger.handlers = [_handler]
api_logger.propagate = False


def _uid_from(request) -> str | None:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        from jose import jwt

        return jwt.decode(auth.split(" ", 1)[1], options={"verify_signature": False}).get("sub")
    except Exception:
        return None


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.perf_counter()
        request_id = uuid4().hex
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception:
            status = 500
            api_logger.info(
                "request",
                extra={
                    "ts": datetime_now_iso(),
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "durationMs": round((time.perf_counter() - start) * 1000, 2),
                    "uid": _uid_from(request),
                    "requestId": request_id,
                },
            )
            raise
        api_logger.info(
            "request",
            extra={
                "ts": datetime_now_iso(),
                "method": request.method,
                "path": request.url.path,
                "status": status,
                "durationMs": round((time.perf_counter() - start) * 1000, 2),
                "uid": _uid_from(request),
                "requestId": request_id,
            },
        )
        response.headers["X-Request-Id"] = request_id
        return response


def datetime_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
