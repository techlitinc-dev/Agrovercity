from datetime import datetime, timezone
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.core import cache
from app.core import db
from app.core.deps import current_user_id
from app.core.security import verify_mpin
from app.models.consents import ConsentsIn, ConsentsOut
from app.models.user import VALID_PROFILES, FarmBoundaryRequest, LinkProfileRequest, UserUpdateRequest
from app.services import consents as consents_service
from app.services import purge as purge_service
from app.services.profile_routes import DEFAULT_HOME
from app.services import users as users_service

router = APIRouter(prefix="/users", tags=["users"])


class DeleteMeRequest(BaseModel):
    mpin: str


class DeviceRegisterRequest(BaseModel):
    fcmToken: str
    platform: str = Field(pattern=r"^(android|web)$")
    locale: str = "hi"


def _strip_mpin_hash(user: dict) -> dict:
    return {k: v for k, v in user.items() if k != "mpinHash"}


def _require_role(user: dict, *roles):
    if user.get("activeProfile") not in roles:
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN_ROLE", "message": "Active profile is not permitted for this action", "fieldErrors": {}},
        )


async def _get_user_or_404(uid: str) -> dict:
    user = await users_service.get_user(uid)
    if user is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "User not found", "fieldErrors": {}},
        )
    return user


@router.get("/me")
async def get_me(uid: str = Depends(current_user_id)):
    user = await _get_user_or_404(uid)
    role_profiles = await users_service.get_role_profiles(uid)
    return {**_strip_mpin_hash(user), "roleProfiles": role_profiles}


@router.put("/me")
async def update_me(body: UserUpdateRequest, uid: str = Depends(current_user_id)):
    user = await _get_user_or_404(uid)
    for key, value in body.model_dump(exclude_none=True).items():
        user[key] = value
    user = await users_service.save_user(uid, user)
    return _strip_mpin_hash(user)


@router.put("/me/farm-boundary")
async def save_farm_boundary(body: FarmBoundaryRequest, uid: str = Depends(current_user_id)):
    user = await _get_user_or_404(uid)
    if "farmer" not in user.get("linkedProfiles", []):
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN_ROLE", "message": "Farmer profile required for farm boundary", "fieldErrors": {}},
        )
    user["farmBoundaryPoints"] = [p.model_dump() for p in body.farmBoundaryPoints]
    user["landAreaAcres"] = body.landAreaAcres
    if body.khasraNumber is not None:
        user["khasraNumber"] = body.khasraNumber
    user = await users_service.save_user(uid, user)
    return _strip_mpin_hash(user)


@router.post("/me/profiles")
async def link_profile(body: LinkProfileRequest, uid: str = Depends(current_user_id)):
    user = await _get_user_or_404(uid)
    if body.profileType not in VALID_PROFILES:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_PROFILE_TYPE", "message": "Invalid profile type", "fieldErrors": {"profileType": "unknown profile type"}},
        )
    if body.profileType in user.get("linkedProfiles", []):
        raise HTTPException(
            status_code=409,
            detail={"code": "PROFILE_ALREADY_LINKED", "message": "Profile is already linked", "fieldErrors": {}},
        )
    user["linkedProfiles"].append(body.profileType)
    user = await users_service.save_user(uid, user)
    return _strip_mpin_hash(user)


@router.delete("/me/profiles/{profile_type}")
async def unlink_profile(profile_type: str, uid: str = Depends(current_user_id)):
    user = await _get_user_or_404(uid)
    if profile_type not in user.get("linkedProfiles", []):
        raise HTTPException(
            status_code=404,
            detail={"code": "PROFILE_NOT_LINKED", "message": "Profile is not linked", "fieldErrors": {}},
        )
    if len(user["linkedProfiles"]) == 1:
        raise HTTPException(
            status_code=409,
            detail={"code": "LAST_PROFILE", "message": "कम से कम एक प्रोफाइल आवश्यक है", "fieldErrors": {}},
        )
    was_primary = profile_type == user.get("primaryProfile")
    was_active = profile_type == user.get("activeProfile")
    user["linkedProfiles"].remove(profile_type)
    if was_primary:
        user["primaryProfile"] = user["linkedProfiles"][0]
    if was_active:
        user["activeProfile"] = user["primaryProfile"]
    user = await users_service.save_user(uid, user)
    return _strip_mpin_hash(user)


@router.post("/me/profiles/{profile_type}/activate")
async def activate_profile(profile_type: str, uid: str = Depends(current_user_id)):
    user = await _get_user_or_404(uid)
    if profile_type not in user.get("linkedProfiles", []):
        raise HTTPException(
            status_code=404,
            detail={"code": "PROFILE_NOT_LINKED", "message": "Profile is not linked", "fieldErrors": {}},
        )
    user["activeProfile"] = profile_type
    user = await users_service.save_user(uid, user)
    return {
        "activeProfile": profile_type,
        "defaultHomeRoute": DEFAULT_HOME[profile_type],
        "user": _strip_mpin_hash(user),
    }


@router.put("/me/profiles/{profile_type}/primary")
async def set_primary_profile(profile_type: str, uid: str = Depends(current_user_id)):
    user = await _get_user_or_404(uid)
    if profile_type not in user.get("linkedProfiles", []):
        raise HTTPException(
            status_code=404,
            detail={"code": "PROFILE_NOT_LINKED", "message": "Profile is not linked", "fieldErrors": {}},
        )
    user["primaryProfile"] = profile_type
    user = await users_service.save_user(uid, user)
    return _strip_mpin_hash(user)


@router.delete("/me")
async def delete_me(body: DeleteMeRequest, uid: str = Depends(current_user_id)):
    redis = await cache.get_redis()
    attempts_key = f"del_attempts:{uid}"
    attempts = await redis.incr(attempts_key)
    if attempts == 1:
        await redis.expire(attempts_key, 3600)
    if attempts > 3:
        raise HTTPException(
            status_code=429,
            detail={"code": "TOO_MANY_ATTEMPTS", "message": "Too many attempts — try again later", "fieldErrors": {}},
        )

    user = await users_service.get_user(uid)
    if user is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "User not found", "fieldErrors": {}})
    if user.get("mpinHash") is None:
        raise HTTPException(status_code=409, detail={"code": "MPIN_NOT_SET", "message": "MPIN has not been set for this account", "fieldErrors": {}})
    if not verify_mpin(body.mpin, user["mpinHash"]):
        raise HTTPException(status_code=401, detail={"code": "WRONG_MPIN", "message": "Incorrect MPIN", "fieldErrors": {}})

    purged = await purge_service.purge_user(uid)
    await cache.cache_delete(attempts_key)
    return {"deleted": True, "purged": purged}


async def register_device(body: DeviceRegisterRequest, uid: str = Depends(current_user_id)):
    token_hash = sha256(body.fcmToken.encode()).hexdigest()[:16]
    await db.set_subdoc_at(
        f"users/{uid}/devices",
        token_hash,
        {
            "id": token_hash,
            "fcmTokenHash": token_hash,
            "platform": body.platform,
            "locale": body.locale,
            "lastSeenAt": datetime.now(timezone.utc).isoformat(),
        },
    )
    return {"registered": True}


async def delete_device(token_hash: str, uid: str = Depends(current_user_id)):
    await db.delete_subdoc_at(f"users/{uid}/devices", token_hash)
    return Response(status_code=204)


devices_router = APIRouter(tags=["devices"])


@devices_router.post("/devices", status_code=201)
async def register_device_top(body: DeviceRegisterRequest, uid: str = Depends(current_user_id)):
    return await register_device(body, uid)


@devices_router.delete("/devices/{token_hash}", status_code=204)
async def delete_device_top(token_hash: str, uid: str = Depends(current_user_id)):
    return await delete_device(token_hash, uid)


@router.get("/me/consents")
async def get_consents(uid: str = Depends(current_user_id)):
    consents = await consents_service.get_consents(uid)
    return ConsentsOut(**consents, updatedAt=consents.get("updatedAt", ""))


@router.put("/me/consents")
async def put_consents(body: ConsentsIn, uid: str = Depends(current_user_id)):
    doc = await consents_service.put_consents(uid, body.model_dump())
    return ConsentsOut(**body.model_dump(), updatedAt=doc["updatedAt"])
