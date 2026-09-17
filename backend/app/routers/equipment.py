from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from app.core import db
from app.core.deps import require_roles
from app.models.equipment import BookSlotRequest
from app.services import coins as coins_service
from app.services import equipment as equipment_service
from app.services import sms as sms_service

router = APIRouter(prefix="/equipment", tags=["equipment"])

VIEW_ROLES = ("farmer", "equipmentRental")
BOOK_ROLE = ("farmer",)
MAX_SLOTS_PER_DAY = 2


@router.get("")
async def list_equipment(type: str | None = None, lat: float | None = None, lng: float | None = None, user: dict = Depends(require_roles(*VIEW_ROLES))):
    docs = await db.query("equipment", [], limit=1000)
    docs = [d for d in docs if d.get("active", True) and d.get("docStatus") == "verified"]
    if type:
        docs = [d for d in docs if d.get("type") == type]
    docs = [{**d, **await _provider_rating(d.get("ownerId"))} for d in docs]
    return {"data": docs}


async def _provider_rating(owner_id: str | None) -> dict:
    if not owner_id:
        return {"ratingAvg": None, "ratingCount": 0}
    agg = await db.get_doc("provider_ratings", owner_id)
    if agg is None:
        return {"ratingAvg": None, "ratingCount": 0}
    return {"ratingAvg": agg.get("ratingAvg"), "ratingCount": agg.get("ratingCount", 0)}


@router.get("/{equipment_id}/slots")
async def get_slots(equipment_id: str, date: str | None = None, user: dict = Depends(require_roles(*VIEW_ROLES))):
    equipment = await db.get_doc("equipment", equipment_id)
    if equipment is None or equipment.get("docStatus") != "verified":
        raise HTTPException(
            status_code=404,
            detail={"code": "EQUIPMENT_NOT_FOUND", "message": "Equipment not found", "fieldErrors": {}},
        )
    date_str = date or equipment_service.today_ist().isoformat()
    slots = await equipment_service.get_or_generate_slots(equipment, date_str)
    return {"data": slots}


@router.post("/slots/{slot_id}/book")
async def book_slot(slot_id: str, body: BookSlotRequest, user: dict = Depends(require_roles(*BOOK_ROLE))):
    slot = await db.get_doc("equipment_slots", slot_id)
    if slot is None or slot.get("status") != "available":
        raise HTTPException(
            status_code=409,
            detail={"code": "SLOT_UNAVAILABLE", "message": "Slot is not available", "fieldErrors": {}},
        )
    bookings = await db.query("equipment_bookings", [("userId", "==", user["id"])], limit=1000)
    same_day = [b for b in bookings if b.get("date") == slot["date"] and b.get("status") in {"booked", "pending"}]
    if len(same_day) >= MAX_SLOTS_PER_DAY:
        raise HTTPException(
            status_code=409,
            detail={"code": "MAX_SLOTS_PER_DAY", "message": "एक दिन में अधिकतम 2 स्लॉट बुक कर सकते हैं", "fieldErrors": {}},
        )
    equipment = await db.get_doc("equipment", slot["equipmentId"])
    if equipment is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "EQUIPMENT_NOT_FOUND", "message": "Equipment not found", "fieldErrors": {}},
        )
    status = "booked" if equipment.get("ownerType") == "fpo" else "pending"
    booking = await equipment_service.create_booking_for_user(user["id"], body.farmerName, slot, equipment, status)

    coins_awarded = await coins_service.award_coins(user["id"], equipment_service.BOOKING_COINS, "equipment_booking", slot["id"])
    return {"booking": booking, "status": status, "agriCoinsEarned": coins_awarded}


@router.post("/slots/{slot_id}/waitlist")
async def join_waitlist(slot_id: str, user: dict = Depends(require_roles(*BOOK_ROLE))):
    waitlist_id = f"{slot_id}_{user['id']}"
    existing = await db.get_doc("equipment_waitlists", waitlist_id)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={"code": "ALREADY_WAITLISTED", "message": "Already on the waitlist for this slot", "fieldErrors": {}},
        )
    await db.set_doc(
        "equipment_waitlists",
        waitlist_id,
        {"id": waitlist_id, "slotId": slot_id, "userId": user["id"], "createdAt": datetime.now(equipment_service.IST).isoformat()},
    )
    return {"ok": True}


@router.delete("/bookings/{booking_id}")
async def cancel_booking(booking_id: str, user: dict = Depends(require_roles(*BOOK_ROLE))):
    booking = await db.get_doc("equipment_bookings", booking_id)
    if booking is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "BOOKING_NOT_FOUND", "message": "Booking not found", "fieldErrors": {}},
        )
    if booking.get("userId") != user["id"]:
        raise HTTPException(
            status_code=403,
            detail={"code": "NOT_BOOKING_OWNER", "message": "Booking does not belong to this user", "fieldErrors": {}},
        )
    if booking.get("status") == "cancelled":
        raise HTTPException(
            status_code=409,
            detail={"code": "ILLEGAL_TRANSITION", "message": "Booking is already cancelled", "fieldErrors": {}},
        )
    start = equipment_service.parse_slot_start(booking["slotName"], booking["date"])
    now_ist = datetime.now(equipment_service.IST)
    if now_ist > start - equipment_service.CANCEL_WINDOW:
        raise HTTPException(
            status_code=409,
            detail={"code": "CANCEL_WINDOW_CLOSED", "message": "Cancellation window (2 hours before start) has closed", "fieldErrors": {}},
        )
    booking["status"] = "cancelled"
    await db.set_doc("equipment_bookings", booking_id, booking)
    owner = await db.get_doc("users", (await db.get_doc("equipment", booking["equipmentId"]) or {}).get("ownerId"))
    owner_phone = (owner or {}).get("phone")
    if owner_phone:
        await sms_service.get_sms_sender().send(
            owner_phone,
            "equipment_cancel_owner",
            {"equipment": (await db.get_doc("equipment", booking["equipmentId"]) or {}).get("name", ""), "date": booking["date"], "slot": booking["slotName"]},
        )
    slot = await db.get_doc("equipment_slots", booking["slotId"])
    equipment = await db.get_doc("equipment", booking["equipmentId"])
    promoted_uid = None
    if slot is not None and equipment is not None:
        slot["status"] = "available"
        slot["bookedByName"] = None
        await db.set_doc("equipment_slots", slot["id"], slot)
        promoted_uid = await equipment_service.promote_waitlist_head(slot, equipment)
    return {"ok": True, "promotedUserId": promoted_uid}
