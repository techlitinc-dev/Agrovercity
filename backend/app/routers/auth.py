from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from firebase_admin import auth as fb_auth
from pydantic import ValidationError

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
    RegisterResponse,
    TokenPair,
)
from app.models.role_profiles import ROLE_PROFILE_MODELS
from app.models.user import VALID_PROFILES, RegisterRequest
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


def _validate_register(body: RegisterRequest) -> dict[str, object]:
    if not body.profiles:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_PROFILE_TYPE", "message": "profiles must not be empty", "fieldErrors": {"profiles": "at least one profile required"}},
        )
    field_errors = {}
    for p in body.profiles:
        if p not in VALID_PROFILES:
            field_errors["profiles"] = f"invalid profile type: {p}"
    if field_errors:
        raise HTTPException(status_code=422, detail={"code": "INVALID_PROFILE_TYPE", "message": "Invalid profile type", "fieldErrors": field_errors})
    if body.primaryProfile not in body.profiles:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_PROFILE_TYPE", "message": "primaryProfile must be in profiles", "fieldErrors": {"primaryProfile": "must be one of profiles"}},
        )
    role_parsed: dict[str, object] = {}
    if body.roleProfiles:
        for ptype, data in body.roleProfiles.items():
            if ptype not in ROLE_PROFILE_MODELS or ptype not in body.profiles:
                field_errors[ptype] = "unknown or unlinked role profile"
                continue
            try:
                role_parsed[ptype] = ROLE_PROFILE_MODELS[ptype](**data)
            except ValidationError:
                field_errors[ptype] = "invalid role profile fields"
        if field_errors:
            raise HTTPException(status_code=422, detail={"code": "INVALID_ROLE_PROFILE", "message": "Invalid role profile", "fieldErrors": field_errors})
    return role_parsed


@router.post("/register", response_model=RegisterResponse)
async def register(body: RegisterRequest):
    try:
        decoded = fb_auth.verify_id_token(body.idToken)
    except fb_auth.InvalidIdTokenError:
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_FIREBASE_TOKEN", "message": "Firebase ID token verification failed", "fieldErrors": {}},
        )
    uid = decoded["uid"]
    validate_mpin_format(body.mpin)
    if body.phone != _normalize_phone(decoded.get("phone_number")):
        raise HTTPException(
            status_code=400,
            detail={"code": "PHONE_MISMATCH", "message": "Phone does not match the verified Firebase token", "fieldErrors": {"phone": "does not match verified phone"}},
        )
    role_parsed = _validate_register(body)

    user = await users_service.get_user(uid)
    if user is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "User must call /auth/firebase-verify before registering", "fieldErrors": {}},
        )

    referral_applied = False
    if body.referralCode:
        referrer = await users_service.find_user_by_referral_code(body.referralCode)
        if referrer is None or referrer.get("id") == uid:
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_REFERRAL_CODE", "message": "Unknown referral code", "fieldErrors": {"referralCode": "unknown code"}},
            )

    user.update(
        {
            "name": body.name,
            "phone": body.phone,
            "state": body.state,
            "district": body.district,
            "tehsil": body.tehsil,
            "village": body.village,
            "landAreaAcres": body.landAreaAcres,
            "soilType": body.soilType,
            "irrigationType": body.irrigationType,
            "activeCrops": body.crops,
            "linkedProfiles": body.profiles,
            "primaryProfile": body.primaryProfile,
            "activeProfile": body.primaryProfile,
            "mpinHash": hash_mpin(body.mpin),
        }
    )
    user = await users_service.save_user(uid, user)

    now_iso = datetime.now(timezone.utc).isoformat()
    for ptype, variant in role_parsed.items():
        await users_service.set_role_profile(uid, ptype, {**variant.model_dump(exclude_none=True), "createdAt": now_iso})

    if body.referralCode:
        await users_service.save_referral_attribution(
            uid,
            {
                "referrerUid": referrer["id"],
                "referredUid": uid,
                "code": body.referralCode,
                "status": "pending",
                "createdAt": now_iso,
            },
        )
        referral_applied = True
    # Coin award for the referrer happens Day 13 — attribution only today.

    return RegisterResponse(
        accessToken=tokens_service.create_access_token(uid),
        refreshToken=tokens_service.create_refresh_token(uid),
        isNewUser=False,
        user=_strip_mpin_hash(user),
        referral={"applied": referral_applied},
    )
