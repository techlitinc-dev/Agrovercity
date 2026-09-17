import time

from fastapi import HTTPException
from jose import JWTError, jwt

from app.core.config import settings


def _encode(user_id: str, token_type: str, ttl_seconds: int) -> str:
    now = int(time.time())
    payload = {"sub": user_id, "type": token_type, "iat": now, "exp": now + ttl_seconds}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str) -> str:
    return _encode(user_id, "access", settings.jwt_access_ttl_minutes * 60)


def create_refresh_token(user_id: str) -> str:
    return _encode(user_id, "refresh", settings.jwt_refresh_ttl_days * 86400)


def decode_token(token: str, expected_type: str) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_TOKEN", "message": "Invalid or expired token", "fieldErrors": {}},
        )
    if payload.get("type") != expected_type:
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_TOKEN", "message": "Invalid token type", "fieldErrors": {}},
        )
    return payload["sub"]
