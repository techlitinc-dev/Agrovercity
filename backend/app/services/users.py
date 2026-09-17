from datetime import datetime, timezone

from app.core.db import get_db, get_doc, query, set_doc

NEW_USER_TEMPLATE = {
    "id": "",
    "phone": "",
    "name": "",
    "vernacularName": "",
    "village": "",
    "tehsil": "",
    "district": "",
    "state": "",
    "landAreaAcres": 0,
    "soilType": "",
    "irrigationType": "",
    "kisanCreditScore": 0,
    "creditTier": "",
    "krishiRatnaLevel": 1,
    "krishiRatnaTitle": "Krishi Shishya",
    "streakDays": 0,
    "agriCoins": 0,
    "bankName": "",
    "kccLimit": 0,
    "activeCrops": [],
    "farmBoundaryPoints": [],
    "linkedProfiles": ["farmer"],
    "primaryProfile": "farmer",
    "activeProfile": "farmer",
    "mpinHash": None,
    "createdAt": "",
}


def referral_code_for(uid: str) -> str:
    return f"ref_{uid[:8]}"


def _new_user_doc(uid: str, phone: str) -> dict:
    doc = dict(NEW_USER_TEMPLATE)
    doc["id"] = uid
    doc["phone"] = phone
    doc["referralCode"] = referral_code_for(uid)
    doc["createdAt"] = datetime.now(timezone.utc).isoformat()
    return doc


async def _backfill_referral_code(uid: str, user: dict) -> dict:
    if not user.get("referralCode"):
        user["referralCode"] = referral_code_for(uid)
        await set_doc("users", uid, user)
    return user


async def upsert_user_from_firebase(uid: str, phone: str) -> tuple[dict, bool]:
    user = await get_doc("users", uid)
    if user is None:
        user = _new_user_doc(uid, phone)
        await set_doc("users", uid, user)
        return user, True
    user = await _backfill_referral_code(uid, user)
    return user, False


async def get_user(uid: str) -> dict | None:
    user = await get_doc("users", uid)
    if user is not None:
        user = await _backfill_referral_code(uid, user)
    return user


async def save_user(uid: str, data: dict) -> dict:
    await set_doc("users", uid, data)
    return data


async def set_mpin_hash(uid: str, mpin_hash: str):
    user = await get_doc("users", uid)
    if user is None:
        return
    user["mpinHash"] = mpin_hash
    await set_doc("users", uid, user)


async def find_user_by_referral_code(code: str) -> dict | None:
    users = await query("users", [("referralCode", "==", code)], limit=1)
    return users[0] if users else None


async def save_referral_attribution(referred_uid: str, data: dict):
    await set_doc("referral_attributions", referred_uid, data)


async def set_role_profile(uid: str, profile_type: str, data: dict):
    await (
        get_db()
        .collection("users")
        .document(uid)
        .collection("role_profiles")
        .document(profile_type)
        .set(data)
    )


async def get_role_profiles(uid: str) -> dict[str, dict]:
    snaps = await get_db().collection("users").document(uid).collection("role_profiles").get()
    return {s.id: s.to_dict() for s in snaps}
