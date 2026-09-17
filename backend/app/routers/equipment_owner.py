from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.core import db
from app.core.deps import require_roles
from app.models.equipment import EquipmentUpsertRequest, RejectEquipmentBookingRequest
from app.services import equipment as equipment_service

router = APIRouter(prefix="/equipment", tags=["equipment-owner"])

OWNER_ROLE = ("equipmentRental",)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _get_own_equipment_or_403(equipment_id: str, uid: str) -> dict:
    equipment = await db.get_doc("equipment", equipment_id)
    if equipment is None or equipment.get("ownerId") != uid:
        raise HTTPException(
            status_code=403,
            detail={"code": "NOT_EQUIPMENT_OWNER", "message": "Equipment does not belong to this owner", "fieldErrors": {}},
        )
    return equipment


@router.post("")
async def create_equipment(body: EquipmentUpsertRequest, user: dict = Depends(require_roles(*OWNER_ROLE))):
    equipment_service.validate_slot_template(body.slotTemplate)
    equipment_id = f"eq_{uuid4().hex[:10]}"
    doc = {
        "id": equipment_id,
        **body.model_dump(),
        "ownerType": "private",
        "ownerId": user["id"],
        "active": True,
        "distanceKm": 0,
        # Admin verify/reject action lives in the admin KYC queue (Day 14, item A1).
        "docStatus": "pending",
        "rejectionReason": None,
        "createdAt": _now_iso(),
    }
    await db.set_doc("equipment", equipment_id, doc)
    return doc


@router.put("/{equipment_id}")
async def update_equipment(equipment_id: str, body: EquipmentUpsertRequest, user: dict = Depends(require_roles(*OWNER_ROLE))):
    equipment = await _get_own_equipment_or_403(equipment_id, user["id"])
    equipment_service.validate_slot_template(body.slotTemplate)
    equipment.update(body.model_dump())
    await db.set_doc("equipment", equipment_id, equipment)
    return equipment


@router.get("/owner/fleet")
async def owner_fleet(user: dict = Depends(require_roles(*OWNER_ROLE))):
    machines = await db.query("equipment", [("ownerId", "==", user["id"])], limit=1000)
    today = equipment_service.today_ist()
    monday = today - timedelta(days=today.weekday())
    week_dates = {(monday + timedelta(days=i)).isoformat() for i in range(7)}
    rows = []
    for machine in machines:
        slots = await db.query("equipment_slots", [("equipmentId", "==", machine["id"])], limit=1000)
        week_slots = [s for s in slots if s.get("date") in week_dates and s.get("status") in {"booked", "pending"}]
        rows.append(
            {
                "equipmentId": machine["id"],
                "name": machine.get("name"),
                "bookedHoursThisWeek": len(week_slots) * 4,
                "weeklyIncome": sum(s.get("priceRupees", 0) for s in week_slots),
                "status": "active" if machine.get("active", True) else "inactive",
                "docStatus": machine.get("docStatus"),
            }
        )
    return {"data": rows}


@router.get("/bookings/pending")
async def pending_bookings(user: dict = Depends(require_roles(*OWNER_ROLE))):
    machines = await db.query("equipment", [("ownerId", "==", user["id"])], limit=1000)
    machine_names = {m["id"]: m.get("name") for m in machines}
    bookings = await db.query("equipment_bookings", [], limit=1000)
    rows = []
    for b in bookings:
        if b.get("status") != "pending" or b.get("equipmentId") not in machine_names:
            continue
        rows.append(
            {
                "bookingId": b["id"],
                "equipmentId": b["equipmentId"],
                "equipmentName": machine_names[b["equipmentId"]],
                "farmerName": b.get("farmerName"),
                "date": b.get("date"),
                "slotName": b.get("slotName"),
                "priceRupees": b.get("priceRupees"),
                "createdAt": b.get("createdAt"),
            }
        )
    return {"data": rows}


@router.post("/bookings/{booking_id}/approve")
async def approve_booking(booking_id: str, user: dict = Depends(require_roles(*OWNER_ROLE))):
    booking = await db.get_doc("equipment_bookings", booking_id)
    if booking is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "BOOKING_NOT_FOUND", "message": "Booking not found", "fieldErrors": {}},
        )
    await _get_own_equipment_or_403(booking.get("equipmentId"), user["id"])
    if booking.get("status") != "pending":
        raise HTTPException(
            status_code=409,
            detail={"code": "ILLEGAL_TRANSITION", "message": f"Cannot approve a booking in status {booking.get('status')}", "fieldErrors": {}},
        )
    booking["status"] = "booked"
    await db.set_doc("equipment_bookings", booking_id, booking)
    slot = await db.get_doc("equipment_slots", booking["slotId"])
    if slot is not None:
        slot["status"] = "booked"
        slot["bookedByName"] = booking.get("farmerName")
        await db.set_doc("equipment_slots", slot["id"], slot)
    await equipment_service.notify_equipment_booking(
        booking["userId"], "बुकिंग स्वीकृत", "आपकी मशीन बुकिंग स्वीकृत हो गई", booking_id, "booking_accepted"
    )
    return booking


@router.post("/bookings/{booking_id}/reject")
async def reject_booking(booking_id: str, body: RejectEquipmentBookingRequest, user: dict = Depends(require_roles(*OWNER_ROLE))):
    if body.reason is None or len(body.reason.strip()) < 3:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "reason must be at least 3 characters", "fieldErrors": {"reason": "must be at least 3 characters"}},
        )
    booking = await db.get_doc("equipment_bookings", booking_id)
    if booking is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "BOOKING_NOT_FOUND", "message": "Booking not found", "fieldErrors": {}},
        )
    equipment = await _get_own_equipment_or_403(booking.get("equipmentId"), user["id"])
    if booking.get("status") != "pending":
        raise HTTPException(
            status_code=409,
            detail={"code": "ILLEGAL_TRANSITION", "message": f"Cannot reject a booking in status {booking.get('status')}", "fieldErrors": {}},
        )
    booking["status"] = "rejected"
    booking["rejectionReason"] = body.reason
    await db.set_doc("equipment_bookings", booking_id, booking)
    slot = await db.get_doc("equipment_slots", booking["slotId"])
    promoted_uid = None
    if slot is not None:
        slot["status"] = "available"
        slot["bookedByName"] = None
        await db.set_doc("equipment_slots", slot["id"], slot)
        promoted_uid = await equipment_service.promote_waitlist_head(slot, equipment)
    await equipment_service.notify_equipment_booking(
        booking["userId"], "बुकिंग अस्वीकृत", f"आपकी मशीन बुकिंग अस्वीकृत: {body.reason}", booking_id, "booking_rejected"
    )
    if promoted_uid:
        await equipment_service.notify_equipment_booking(
            promoted_uid, "स्लॉट उपलब्ध", "वेटलिस्ट से आपकी बुकिंग प्रोमोट हुई है", slot["id"] if slot else booking_id, "waitlist_promoted"
        )
    return {"ok": True, "promotedUserId": promoted_uid}
