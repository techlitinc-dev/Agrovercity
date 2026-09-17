from datetime import datetime, timezone

from app.core.db import get_doc, set_doc

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


def _new_user_doc(uid: str, phone: str) -> dict:
    doc = dict(NEW_USER_TEMPLATE)
    doc["id"] = uid
    doc["phone"] = phone
    doc["createdAt"] = datetime.now(timezone.utc).isoformat()
    return doc


async def upsert_user_from_firebase(uid: str, phone: str) -> tuple[dict, bool]:
    user = await get_doc("users", uid)
    if user is None:
        user = _new_user_doc(uid, phone)
        await set_doc("users", uid, user)
        return user, True
    return user, False


async def get_user(uid: str) -> dict | None:
    return await get_doc("users", uid)


async def set_mpin_hash(uid: str, mpin_hash: str):
    user = await get_doc("users", uid)
    if user is None:
        return
    user["mpinHash"] = mpin_hash
    await set_doc("users", uid, user)
