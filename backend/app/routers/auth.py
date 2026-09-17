from fastapi import APIRouter, Depends, HTTPException
from firebase_admin import auth as fb_auth

from app.core.deps import current_user_id
from app.core.security import hash_mpin, validate_mpin_format, verify_mpin
from app.models.auth import (
    AuthResponse,
    FirebaseVerifyRequest,
    MpinResetRequest,
    MpinSetRequest,
    MpinVerifyRequest,
    OkResponse,
    RefreshRequest,
    TokenPair,
)
from app.services import tokens as tokens_service
from app.services import users as users_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _normalize_phone(phone: str | None) -> str:
    if not phone:
        return ""
    if not phone.startswith("+"):
        return f"+91{phone}"
    return phone


def _strip_mpin_hash(user: dict) -> dict:
    return {k: v for k, v in user.items() if k != "mpinHash"}


@router.post("/firebase-verify", response_model=AuthResponse)
async def firebase_verify(body: FirebaseVerifyRequest):
    try:
        decoded = fb_auth.verify_id_token(body.idToken)
    except fb_auth.InvalidIdTokenError:
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_FIREBASE_TOKEN", "message": "Firebase ID token verification failed", "fieldErrors": {}},
        )
    uid = decoded["uid"]
    phone = _normalize_phone(decoded.get("phone_number"))
    user, is_new = await users_service.upsert_user_from_firebase(uid, phone)
    return AuthResponse(
        accessToken=tokens_service.create_access_token(uid),
        refreshToken=tokens_service.create_refresh_token(uid),
        isNewUser=is_new,
        user=_strip_mpin_hash(user),
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest):
    uid = tokens_service.decode_token(body.refreshToken, "refresh")
    return TokenPair(
        accessToken=tokens_service.create_access_token(uid),
        refreshToken=tokens_service.create_refresh_token(uid),
    )


@router.post("/mpin/set", response_model=OkResponse)
async def mpin_set(body: MpinSetRequest, uid: str = Depends(current_user_id)):
    validate_mpin_format(body.mpin)
    await users_service.set_mpin_hash(uid, hash_mpin(body.mpin))
    return OkResponse()


@router.post("/mpin/verify", response_model=OkResponse)
async def mpin_verify(body: MpinVerifyRequest, uid: str = Depends(current_user_id)):
    user = await users_service.get_user(uid)
    if user is None or user.get("mpinHash") is None:
        raise HTTPException(
            status_code=409,
            detail={"code": "MPIN_NOT_SET", "message": "MPIN has not been set for this account", "fieldErrors": {}},
        )
    if not verify_mpin(body.mpin, user["mpinHash"]):
        raise HTTPException(
            status_code=401,
            detail={"code": "WRONG_MPIN", "message": "Incorrect MPIN", "fieldErrors": {}},
        )
    return OkResponse()


@router.post("/mpin/reset", response_model=OkResponse)
async def mpin_reset(body: MpinResetRequest):
    validate_mpin_format(body.newMpin)
    try:
        decoded = fb_auth.verify_id_token(body.idToken)
    except fb_auth.InvalidIdTokenError:
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_FIREBASE_TOKEN", "message": "Firebase ID token verification failed", "fieldErrors": {}},
        )
    uid = decoded["uid"]
    user = await users_service.get_user(uid)
    if user is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "User not found", "fieldErrors": {}},
        )
    await users_service.set_mpin_hash(uid, hash_mpin(body.newMpin))
    return OkResponse()
