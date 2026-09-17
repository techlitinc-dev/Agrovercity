from uuid import uuid4

from app.core import db
from app.models.consents import ConsentRequiredError

DEFAULTS = {"dataSharing": False, "location": False, "marketing": False}


def _path(uid: str) -> str:
    return f"users/{uid}/consents"


async def get_consents(uid: str) -> dict:
    doc = await db.get_subdoc_at(_path(uid), "current")
    if doc is None:
        return dict(DEFAULTS)
    return {k: doc.get(k, DEFAULTS[k]) for k in DEFAULTS}


async def put_consents(uid: str, consents: dict) -> dict:
    old = await get_consents(uid)
    doc = {**consents, "updatedAt": _now_iso()}
    await db.set_subdoc_at(_path(uid), "current", doc)
    for flag in DEFAULTS:
        if old.get(flag) != consents.get(flag):
            await db.set_doc(
                "consent_log",
                str(uuid4()),
                {"userId": uid, "flag": flag, "newValue": consents.get(flag), "at": doc["updatedAt"], "source": "app"},
            )
    return doc


async def require_data_sharing(uid: str) -> None:
    consents = await get_consents(uid)
    if not consents.get("dataSharing"):
        raise ConsentRequiredError("डेटा साझाकरण की सहमति आवश्यक है")


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
