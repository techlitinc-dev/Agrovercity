from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from typing import Literal

from app.core import cache
from app.core import db
from app.core.deps import admin_user
from app.services.claims import STATUS_TEXT, advance_status

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(admin_user)])

CONTENT_COLLECTIONS = {"news", "blogs", "videos", "workshops", "schemes"}
ANALYTICS_CACHE_TTL = 60


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _envelope(data: list[dict], page: int, page_size: int) -> dict:
    total = len(data)
    start = (max(1, page) - 1) * page_size
    return {"data": data[start : start + page_size], "page": page, "pageSize": page_size, "total": total}


@router.post("/login")
async def login(claims: dict = Depends(admin_user)):
    return {"admin": True, "email": claims.get("email"), "uid": claims.get("uid")}


@router.get("/users")
async def list_users(persona: str | None = None, page: int = 1, pageSize: int = 20, claims: dict = Depends(admin_user)):
    users = await db.query("users", [], limit=1000)
    if persona:
        users = [u for u in users if persona in (u.get("linkedProfiles") or [])]
    users.sort(key=lambda u: u.get("createdAt", ""))
    rows = [
        {
            "id": u["id"],
            "name": u.get("name"),
            "phone": u.get("phone"),
            "district": u.get("district"),
            "state": u.get("state"),
            "linkedProfiles": u.get("linkedProfiles", []),
            "activeProfile": u.get("activeProfile"),
            "status": u.get("status", "active"),
            "agriCoins": u.get("agriCoins", 0),
            "createdAt": u.get("createdAt"),
        }
        for u in users
    ]
    return _envelope(rows, page, max(1, min(pageSize, 50)))


@router.put("/users/{user_id}/status")
async def set_user_status(user_id: str, body: dict, claims: dict = Depends(admin_user)):
    user = await db.get_doc("users", user_id)
    if user is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "User not found", "fieldErrors": {}},
        )
    status = body.get("status")
    if status not in {"active", "blocked"}:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "status must be active or blocked", "fieldErrors": {"status": "must be active or blocked"}},
        )
    user["status"] = status
    await db.set_doc("users", user_id, user)
    if status == "blocked":
        import firebase_admin

        firebase_admin.auth.revoke_refresh_tokens(user_id)
    return {"id": user_id, "status": status}


@router.get("/rates/pending")
async def pending_rates(page: int = 1, pageSize: int = 20, claims: dict = Depends(admin_user)):
    docs = await db.query("vyapari_rates_pending", [("status", "==", "pending")], limit=1000)
    return _envelope(docs, page, max(1, min(pageSize, 50)))


async def _pending_rate_or_404(rate_id: str) -> dict:
    rate = await db.get_doc("vyapari_rates_pending", rate_id)
    if rate is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "RATE_NOT_FOUND", "message": "Rate not found", "fieldErrors": {}},
        )
    return rate


@router.post("/rates/{rate_id}/approve")
async def approve_rate(rate_id: str, claims: dict = Depends(admin_user)):
    rate = await _pending_rate_or_404(rate_id)
    rate["status"] = "approved"
    await db.set_doc("vyapari_rates", rate_id, rate)
    await db.set_doc("vyapari_rates_pending", rate_id, rate)
    redis = await cache.get_redis()
    for key in await redis.keys("vyapari_rates:*"):
        await redis.delete(key)
    return {"id": rate_id, "status": "approved"}


@router.post("/rates/{rate_id}/reject")
async def reject_rate(rate_id: str, body: dict, claims: dict = Depends(admin_user)):
    rate = await _pending_rate_or_404(rate_id)
    rate["status"] = "rejected"
    rate["rejectionReason"] = body.get("reason", "")
    await db.set_doc("vyapari_rates_pending", rate_id, rate)
    return {"id": rate_id, "status": "rejected", "rejectionReason": rate["rejectionReason"]}


@router.post("/content/{collection}", status_code=201)
async def create_content(collection: str, body: dict, claims: dict = Depends(admin_user)):
    _check_collection(collection)
    _check_content_body(body)
    doc_id = uuid4().hex
    doc = {"id": doc_id, **body, "createdAt": _now_iso()}
    await db.set_doc(collection, doc_id, doc)
    return doc


@router.put("/content/{collection}/{doc_id}")
async def update_content(collection: str, doc_id: str, body: dict, claims: dict = Depends(admin_user)):
    _check_collection(collection)
    doc = await db.get_doc(collection, doc_id)
    if doc is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": f"{collection}/{doc_id} not found", "fieldErrors": {}},
        )
    doc.update(body)
    await db.set_doc(collection, doc_id, doc)
    return doc


@router.delete("/content/{collection}/{doc_id}", status_code=204)
async def delete_content(collection: str, doc_id: str, claims: dict = Depends(admin_user)):
    _check_collection(collection)
    await db.delete_doc(collection, doc_id)
    return Response(status_code=204)


def _check_collection(collection: str):
    if collection not in CONTENT_COLLECTIONS:
        raise HTTPException(
            status_code=400,
            detail={"code": "UNKNOWN_COLLECTION", "message": "Unknown content collection", "fieldErrors": {"collection": "must be one of news, blogs, videos, workshops, schemes"}},
        )


def _check_content_body(body: dict):
    if "title" not in body and "name" not in body:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "Content requires a title or name", "fieldErrors": {"title": "title or name required"}},
        )
    if "eligibilityRules" in body and not isinstance(body["eligibilityRules"], dict):
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_RULES_JSON", "message": "eligibilityRules must be a JSON object", "fieldErrors": {"eligibilityRules": "must be an object"}},
        )


@router.get("/claims")
async def list_claims(status: str | None = None, page: int = 1, pageSize: int = 20, claims: dict = Depends(admin_user)):
    rows = await db.list_collection_group("insurance_claims")
    items = []
    for entry in rows:
        claim = entry["doc"]
        claim = {**claim, "userId": entry["path"].split("/")[1] if entry["path"] else claim.get("userId")}
        if status is None or claim.get("status") == status:
            items.append(claim)
    items.sort(key=lambda c: c.get("submittedAt", ""), reverse=True)
    return _envelope(items, page, max(1, min(pageSize, 50)))


@router.put("/claims/{user_id}/{claim_id}")
async def advance_claim(user_id: str, claim_id: str, body: dict, claims: dict = Depends(admin_user)):
    claim = await db.get_subdoc_at(f"users/{user_id}/insurance_claims", claim_id)
    if claim is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "CLAIM_NOT_FOUND", "message": "Claim not found", "fieldErrors": {}},
        )
    new_status = body.get("newStatus", "")
    if new_status == "disbursed" and (body.get("approvedAmount") is None or not body.get("dbtTransactionId")):
        raise HTTPException(
            status_code=422,
            detail={"code": "DISBURSAL_FIELDS_REQUIRED", "message": "approvedAmount and dbtTransactionId are required for disbursal", "fieldErrors": {}},
        )
    try:
        claim = await advance_status(claim, new_status, body.get("note", ""), uid=user_id)
    except ValueError:
        raise HTTPException(
            status_code=409,
            detail={"code": "ILLEGAL_STATUS_TRANSITION", "message": f"Cannot move claim to {new_status}", "fieldErrors": {}},
        )
    if new_status == "disbursed":
        claim["approvedAmount"] = body.get("approvedAmount")
        claim["dbtTransactionId"] = body.get("dbtTransactionId")
    await db.set_subdoc_at(f"users/{user_id}/insurance_claims", claim_id, claim)
    return claim


@router.get("/analytics/summary")
async def analytics_summary(claims: dict = Depends(admin_user)):
    redis = await cache.get_redis()
    cached = await redis.get("admin:analytics")
    if cached:
        import json

        return json.loads(cached)

    users = await db.query("users", [], limit=10000)
    personas = ["farmer", "farmLandlord", "transport", "seller", "equipmentRental", "broker"]
    users_by_persona = {p: sum(1 for u in users if p in (u.get("linkedProfiles") or [])) for p in personas}

    equipment_bookings = await db.query("equipment_bookings", [], limit=10000)
    transport_bookings = await db.query("transport_bookings", [], limit=10000)
    vet_bookings = await db.list_collection_group("vet_bookings")

    orders = await db.query("orders", [], limit=10000)

    claim_rows = await db.list_collection_group("insurance_claims")
    claims_by_status: dict[str, int] = {}
    for entry in claim_rows:
        status = entry["doc"].get("status", "unknown")
        claims_by_status[status] = claims_by_status.get(status, 0) + 1

    pending_rates = await db.query("vyapari_rates_pending", [("status", "==", "pending")], limit=10000)

    summary = {
        "totalUsers": len(users),
        "usersByPersona": users_by_persona,
        "bookings": {
            "equipment": len(equipment_bookings),
            "vet": len(vet_bookings),
            "transport": len(transport_bookings),
        },
        "orders": {
            "count": len(orders),
            "gmv": sum(o.get("total", 0) for o in orders),
        },
        "claimsByStatus": claims_by_status,
        "pendingRates": len(pending_rates),
    }
    await redis.set("admin:analytics", _dumps(summary), ex=ANALYTICS_CACHE_TTL)
    return summary


def _dumps(obj) -> str:
    import json

    return json.dumps(obj, default=str)


@router.get("/kyc/pending")
async def kyc_pending(page: int = 1, pageSize: int = 20, claims: dict = Depends(admin_user)):
    rows = []
    vehicles = await db.query("vehicles", [], limit=1000)
    for v in vehicles:
        if v.get("docStatus") == "pending":
            rows.append({"entityId": v["id"], "entityKind": "vehicle", "ownerId": v.get("ownerId"), "ownerName": v.get("registrationNo"), "docs": []})
    equipment = await db.query("equipment", [], limit=1000)
    for e in equipment:
        if e.get("docStatus") == "pending":
            rows.append({"entityId": e["id"], "entityKind": "equipment", "ownerId": e.get("ownerId"), "ownerName": e.get("name"), "docs": []})
    return _envelope(rows, page, max(1, min(pageSize, 50)))


async def _kyc_entity_or_404(entity_id: str) -> tuple[str, dict]:
    for collection, kind in (("vehicles", "vehicle"), ("equipment", "equipment")):
        doc = await db.get_doc(collection, entity_id)
        if doc is not None and doc.get("docStatus") is not None:
            return kind, doc
    raise HTTPException(
        status_code=404,
        detail={"code": "KYC_ENTITY_NOT_FOUND", "message": "KYC entity not found", "fieldErrors": {}},
    )


@router.post("/kyc/{entity_id}/verify")
async def kyc_verify(entity_id: str, claims: dict = Depends(admin_user)):
    kind, doc = await _kyc_entity_or_404(entity_id)
    collection = "vehicles" if kind == "vehicle" else "equipment"
    doc["docStatus"] = "verified"
    doc["verifiedAt"] = _now_iso()
    await db.set_doc(collection, entity_id, doc)
    return doc


@router.post("/kyc/{entity_id}/reject")
async def kyc_reject(entity_id: str, body: dict, claims: dict = Depends(admin_user)):
    kind, doc = await _kyc_entity_or_404(entity_id)
    collection = "vehicles" if kind == "vehicle" else "equipment"
    doc["docStatus"] = "rejected"
    doc["rejectionReason"] = body.get("reason", "")
    await db.set_doc(collection, entity_id, doc)
    return doc


@router.post("/broadcast")
async def broadcast(body: dict, claims: dict = Depends(admin_user)):
    segment = body.get("segment") or {}
    if not (segment.get("role") or segment.get("district")):
        raise HTTPException(
            status_code=422,
            detail={"code": "SEGMENT_REQUIRED", "message": "At least one segment key is required", "fieldErrors": {"segment": "role or district required"}},
        )
    users = await db.query("users", [], limit=10000)
    audience = users
    if segment.get("role"):
        audience = [u for u in audience if segment["role"] in (u.get("linkedProfiles") or [])]
    if segment.get("district"):
        audience = [u for u in audience if u.get("district") == segment["district"]]

    if body.get("dryRun"):
        return {"targetedCount": len(audience)}

    from app.services import fcm as fcm_service

    sent = 0
    for u in audience:
        sent += await fcm_service.send_to_user(
            u["id"],
            body.get("title", ""),
            body.get("body", ""),
            {"type": "broadcast", "deepLink": body.get("deepLink", "")},
        )
    return {"targetedCount": len(audience), "sent": sent}


@router.get("/settlements")
async def admin_settlements(status: str | None = None, page: int = 1, pageSize: int = 20, claims: dict = Depends(admin_user)):
    docs = await db.query("settlements", [], limit=1000)
    if status:
        docs = [d for d in docs if d.get("status") == status]
    docs.sort(key=lambda d: d.get("periodStart", ""), reverse=True)
    return _envelope(docs, page, max(1, min(pageSize, 50)))


class SettleActionIn(BaseModel):
    action: Literal["approve", "mark_paid"]


@router.post("/settlements/{settlement_id}/settle")
async def settle(settlement_id: str, body: SettleActionIn, claims: dict = Depends(admin_user)):
    settlement = await db.get_doc("settlements", settlement_id)
    if settlement is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Settlement not found", "fieldErrors": {}},
        )
    if body.action == "approve":
        if settlement.get("status") != "pending":
            raise HTTPException(
                status_code=409,
                detail={"code": "ILLEGAL_STATUS_TRANSITION", "message": "Only pending settlements can be approved", "fieldErrors": {}},
            )
        settlement["status"] = "approved"
    else:
        if settlement.get("status") != "approved":
            raise HTTPException(
                status_code=409,
                detail={"code": "ILLEGAL_STATUS_TRANSITION", "message": "Only approved settlements can be marked paid", "fieldErrors": {}},
            )
        settlement["status"] = "paid"
        settlement["paidAt"] = _now_iso()
    await db.set_doc("settlements", settlement_id, settlement)
    return settlement


@router.get("/reports")
async def admin_reports(status: str | None = None, page: int = 1, pageSize: int = 20, claims: dict = Depends(admin_user)):
    docs = await db.query("reports", [], limit=1000)
    if status:
        docs = [d for d in docs if d.get("status") == status]
    return _envelope(docs, page, max(1, min(pageSize, 50)))


@router.post("/reports/{report_id}/resolve")
async def resolve_report(report_id: str, body: dict, claims: dict = Depends(admin_user)):
    report = await db.get_doc("reports", report_id)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "REPORT_NOT_FOUND", "message": "Report not found", "fieldErrors": {}},
        )
    action = body.get("action")
    if action not in {"dismiss", "block"}:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "action must be dismiss or block", "fieldErrors": {"action": "must be dismiss or block"}},
        )
    report["status"] = "resolved"
    report["resolution"] = action
    report["resolutionNote"] = body.get("note", "")
    await db.set_doc("reports", report_id, report)
    if action == "block":
        reported = await db.get_doc("users", report.get("reportedId"))
        if reported is not None:
            reported["status"] = "blocked"
            await db.set_doc("users", reported["id"], reported)
            import firebase_admin

            firebase_admin.auth.revoke_refresh_tokens(reported["id"])
    return report
