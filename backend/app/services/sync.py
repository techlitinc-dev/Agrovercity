import hashlib
import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from app.core import db
from app.services import coins as coins_service
from app.services import equipment as equipment_service

logger = logging.getLogger(__name__)

# Photos are NOT replayable via sync — claim bodies carry already-uploaded photo URLs.
REPLAYABLE_PREFIXES = [
    "/v1/equipment/slots/",
    "/v1/vets/",
    "/v1/fpo/pools/",
]
REPLAYABLE_EXACT = {
    "/v1/diary/entries": "handle_diary",
    "/v1/insurance/claims": "handle_claim",
}

SERVER_OWNED_FIELDS = {
    "agriCoins", "agriCoinsEarned", "status", "approvedAmount", "timeline",
    "bankAccountLast4", "kisanCreditScore", "kccLimit", "priceRupees",
}


def _key_hash(key: str) -> str:
    import hashlib

    return hashlib.sha256(key.encode()).hexdigest()


async def already_processed(key: str) -> dict | None:
    doc = await db.get_doc("idempotency_keys", _key_hash(key))
    return doc


async def mark_processed(key: str, result: dict):
    await db.set_doc(
        "idempotency_keys",
        _key_hash(key),
        {"result": result, "processedAt": datetime.now(timezone.utc).isoformat()},
    )


def _strip_server_owned(body: dict) -> dict:
    stripped = {k: v for k, v in body.items() if k not in SERVER_OWNED_FIELDS}
    removed = set(body) - set(stripped)
    if removed:
        logger.warning("Sync replay stripped server-owned fields: %s", sorted(removed))
    return stripped


def _error(status: int, code: str, message: str) -> dict:
    return {"status": "error", "httpStatus": status, "error": {"code": code, "message": message, "fieldErrors": {}}}


async def dispatch(uid: str, op: dict) -> dict:
    key = op.get("idempotencyKey", "")
    prior = await already_processed(key)
    if prior is not None:
        return {"idempotencyKey": key, "status": "duplicate", "httpStatus": prior.get("result", {}).get("httpStatus", 200)}

    method = op.get("method", "")
    path = op.get("path", "")
    if method != "POST":
        result = _error(400, "UNSUPPORTED_METHOD", "Only POST operations are replayable")
    elif not (_match_exact(path) or _match_prefix(path)):
        result = _error(400, "UNSUPPORTED_PATH", "Path is not replayable via sync")
    else:
        body = _strip_server_owned(op.get("body", {}) or {})
        try:
            handler_result, http_status = await _run_handler(path, uid, body)
            result = {"status": "applied", "httpStatus": http_status, "result": handler_result}
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {"code": "ERROR", "message": str(exc.detail), "fieldErrors": {}}
            result = {"status": "error", "httpStatus": exc.status_code, "error": detail}
    await mark_processed(key, result)
    return {"idempotencyKey": key, **result}


def _match_exact(path: str) -> str | None:
    return path if path in REPLAYABLE_EXACT else None


def _match_prefix(path: str) -> str | None:
    for prefix in REPLAYABLE_PREFIXES:
        if path.startswith(prefix):
            return prefix
    return None


async def _run_handler(path: str, uid: str, body: dict) -> tuple[dict, int]:
    if path == "/v1/diary/entries":
        return await _handle_diary(uid, body), 201
    if path == "/v1/insurance/claims":
        return await _handle_claim(uid, body), 201
    if path.startswith("/v1/equipment/slots/"):
        slot_id = path.split("/")[4]
        return await _handle_equipment_book(slot_id, uid, body), 200
    if path.startswith("/v1/vets/") and path.endswith("/book"):
        vet_id = path.split("/")[3]
        return await _handle_vet_book(vet_id, uid, body), 201
    if path.startswith("/v1/fpo/pools/") and path.endswith("/join"):
        pool_id = path.split("/")[4]
        return await _handle_pool_join(pool_id, uid, body), 200
    raise HTTPException(status_code=400, detail={"code": "UNSUPPORTED_PATH", "message": "Path is not replayable", "fieldErrors": {}})


async def _handle_diary(uid: str, body: dict) -> dict:
    entry_id = uuid.uuid4().hex
    doc = {"id": entry_id, **body}
    await db.set_subdoc_at(f"users/{uid}/diary_entries", entry_id, doc)
    awarded = await coins_service.award_coins(uid, 15, "diary_entry", entry_id)
    return {"entry": doc, "agriCoinsEarned": awarded}


async def _handle_claim(uid: str, body: dict) -> dict:
    from app.services.claims import STATUS_TEXT, auto_assign_surveyor, next_claim_number, state_code
    from app.services import users as users_service

    policy = await db.get_subdoc_at(f"users/{uid}/insurance_policies", body.get("policyId", ""))
    if policy is None:
        raise HTTPException(status_code=404, detail={"code": "POLICY_NOT_FOUND", "message": "Policy not found", "fieldErrors": {}})
    user = await users_service.get_user(uid) or {}
    claim_number = await next_claim_number(state_code(user.get("state")))
    surveyor = auto_assign_surveyor(user.get("district", ""))
    claim_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    claim = {
        "id": claim_id,
        "claimNumber": claim_number,
        "policyId": body.get("policyId", ""),
        "cropName": body.get("cropName", ""),
        "calamityType": body.get("calamityType", ""),
        "dateOfDamage": body.get("dateOfDamage", ""),
        "cropStage": body.get("cropStage", ""),
        "estimatedLossPercent": body.get("estimatedLossPercent", 0),
        "requestedAmount": round(policy.get("sumInsured", 0) * body.get("estimatedLossPercent", 0) / 100, 2),
        "approvedAmount": None,
        "status": "intimated",
        "statusText": STATUS_TEXT["intimated"],
        "surveyorName": surveyor["surveyorName"],
        "surveyorPhone": surveyor["surveyorPhone"],
        "surveyorVisitDate": surveyor["surveyorVisitDate"],
        "gpsCoordinates": body.get("gpsCoordinates", ""),
        "village": body.get("village", ""),
        "damagePhotos": body.get("damagePhotos", []),
        "submittedAt": now,
        "dbtTransactionId": None,
        "bankAccountLast4": (user.get("phone") or "")[-4:] or None,
        "timeline": [{"status": "intimated", "at": now, "note": "Claim intimated within 72h window"}],
        "appealCount": 0,
        "rejectionReason": None,
    }
    await db.set_subdoc_at(f"users/{uid}/insurance_claims", claim_id, claim)
    return claim


async def _handle_equipment_book(slot_id: str, uid: str, body: dict) -> dict:
    slot = await db.get_doc("equipment_slots", slot_id)
    if slot is None or slot.get("status") != "available":
        raise HTTPException(status_code=409, detail={"code": "SLOT_UNAVAILABLE", "message": "Slot is not available", "fieldErrors": {}})
    bookings = await db.query("equipment_bookings", [("userId", "==", uid)], limit=1000)
    same_day = [b for b in bookings if b.get("date") == slot.get("date") and b.get("status") in {"booked", "pending"}]
    if len(same_day) >= equipment_service.MAX_SLOTS_PER_DAY:
        raise HTTPException(status_code=409, detail={"code": "MAX_SLOTS_PER_DAY", "message": "एक दिन में अधिकतम 2 स्लॉट बुक कर सकते हैं", "fieldErrors": {}})
    equipment = await db.get_doc("equipment", slot.get("equipmentId"))
    if equipment is None:
        raise HTTPException(status_code=404, detail={"code": "EQUIPMENT_NOT_FOUND", "message": "Equipment not found", "fieldErrors": {}})
    status = "booked" if equipment.get("ownerType") == "fpo" else "pending"
    booking = await equipment_service.create_booking_for_user(uid, body.get("farmerName", "Farmer"), slot, equipment, status)
    await coins_service.award_coins(uid, equipment_service.BOOKING_COINS, "equipment_booking", slot_id)
    return booking


async def _handle_vet_book(vet_id: str, uid: str, body: dict) -> dict:
    vet = await db.get_doc("vets", vet_id)
    if vet is None:
        raise HTTPException(status_code=404, detail={"code": "VET_NOT_FOUND", "message": "Vet not found", "fieldErrors": {}})
    if body.get("visitType") == "farm" and not vet.get("availableForFarmVisit"):
        raise HTTPException(status_code=400, detail={"code": "FARM_VISIT_UNAVAILABLE", "message": "यह डॉक्टर फ़ार्म विज़िट नहीं करते", "fieldErrors": {}})
    booking_id = f"vetbk_{uuid.uuid4().hex[:10]}"
    doc = {
        "id": booking_id,
        "vetId": vet_id,
        "vetName": vet.get("name", ""),
        "visitType": body.get("visitType", "clinic"),
        "slot": body.get("slot", ""),
        "animalType": body.get("animalType", ""),
        "consultationFeeRupees": vet.get("consultationFeeRupees", 0),
        "status": "confirmed",
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    await db.set_subdoc_at(f"users/{uid}/vet_bookings", booking_id, doc)
    return doc


async def _handle_pool_join(pool_id: str, uid: str, body: dict) -> dict:
    pool = await db.get_doc("fpo_pools", pool_id)
    if pool is None:
        raise HTTPException(status_code=404, detail={"code": "POOL_NOT_FOUND", "message": "Pool not found", "fieldErrors": {}})
    units = body.get("units", 1)
    if pool.get("bookedUnits", 0) + units > pool.get("targetUnits", 0):
        raise HTTPException(status_code=409, detail={"code": "POOL_FULL", "message": "Pool target already met", "fieldErrors": {}})
    pool["bookedUnits"] = pool.get("bookedUnits", 0) + units
    await db.set_doc("fpo_pools", pool_id, pool)
    await db.set_subdoc_at(f"fpo_pools/{pool_id}/members", uid, {"units": units, "joinedAt": datetime.now(timezone.utc).isoformat()})
    return pool
