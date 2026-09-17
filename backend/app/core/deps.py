from fastapi import Header, HTTPException

from app.services.tokens import decode_token


async def current_user_id(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"code": "MISSING_TOKEN", "message": "Missing or malformed Authorization header", "fieldErrors": {}},
        )
    token = authorization.split(" ", 1)[1]
    return decode_token(token, "access")
