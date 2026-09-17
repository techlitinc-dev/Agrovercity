from fastapi import Depends, Header, HTTPException

from app.services import users as users_service
from app.services.tokens import decode_token


async def current_user_id(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"code": "MISSING_TOKEN", "message": "Missing or malformed Authorization header", "fieldErrors": {}},
        )
    token = authorization.split(" ", 1)[1]
    return decode_token(token, "access")


def require_roles(*roles):
    async def dependency(user_id: str = Depends(current_user_id)):
        user = await users_service.get_user(user_id)
        if user is None or user.get("activeProfile") not in roles:
            raise HTTPException(
                status_code=403,
                detail={"code": "FORBIDDEN_ROLE", "message": "Active profile is not permitted for this action", "fieldErrors": {}},
            )
        return user

    return dependency


def require_profile(user: dict, *roles):
    """In-request variant for routers that already loaded the user."""
    if user is None or user.get("activeProfile") not in roles:
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN_ROLE", "message": "Active profile is not permitted for this action", "fieldErrors": {}},
        )


async def admin_user(authorization: str | None = Header(default=None)) -> dict:
    """Admin-console guard. The admin console signs in with Firebase Auth
    directly — this route family is the exception to the backend-JWT rule."""
    import firebase_admin

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"code": "MISSING_TOKEN", "message": "Missing or malformed Authorization header", "fieldErrors": {}},
        )
    token = authorization.split(" ", 1)[1]
    try:
        claims = firebase_admin.auth.verify_id_token(token, check_revoked=True)
    except Exception:
        raise HTTPException(
            status_code=401,
            detail={"code": "MISSING_TOKEN", "message": "Invalid admin token", "fieldErrors": {}},
        )
    if claims.get("admin") is not True:
        raise HTTPException(
            status_code=403,
            detail={"code": "ADMIN_REQUIRED", "message": "यह खाता एडमिन नहीं है", "fieldErrors": {}},
        )
    return claims
