import re
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException
from uuid import uuid4

from app.core import db
from app.services.notifications import send_fcm_to_user

IST = timezone(timedelta(hours=5, minutes=30))

# default template mirrors the prototype dummyYantraSlots
DEFAULT_SLOTS = [
    {"slotName": "6:00 AM – 10:00 AM", "duration": "4 hours", "priceRupees": 800, "recommendedTask": "Ploughing, tilling (जुताई)"},
    {"slotName": "10:00 AM – 2:00 PM", "duration": "4 hours", "priceRupees": 800, "recommendedTask": "Sowing, spraying (बुवाई)"},
    {"slotName": "2:00 PM – 6:00 PM", "duration": "4 hours", "priceRupees": 800, "recommendedTask": "Harvesting, transport (कटाई)"},
    {"slotName": "6:00 PM – 10:00 PM", "duration": "4 hours", "priceRupees": 800, "recommendedTask": "Irrigation, light work (सिंचाई)"},
]

SLOT_TEMPLATE_KEYS = {"slotName", "duration", "priceRupees", "recommendedTask"}
BOOKING_COINS = 50
CANCEL_WINDOW = timedelta(hours=2)


def today_ist() -> date:
    return datetime.now(IST).date()


def parse_slot_start(slot_name: str, date_str: str) -> datetime:
    start_str = re.split(r"[–-]", slot_name)[0].strip()
    start_time = datetime.strptime(start_str, "%I:%M %p")
    day = datetime.strptime(date_str, "%Y-%m-%d")
    return datetime.combine(day.date(), start_time.time(), tzinfo=IST)


def validate_slot_template(template: list[dict] | None):
    if template is None:
        return
    if not 1 <= len(template) <= 8:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "slotTemplate must have 1–8 entries", "fieldErrors": {"slotTemplate": "must have 1–8 entries"}},
        )
    for entry in template:
        if not SLOT_TEMPLATE_KEYS.issubset(entry.keys()):
            raise HTTPException(
                status_code=422,
                detail={"code": "VALIDATION_ERROR", "message": "each slot needs slotName, duration, priceRupees, recommendedTask", "fieldErrors": {"slotTemplate": "missing keys"}},
            )


async def get_or_generate_slots(equipment: dict, date_str: str) -> list[dict]:
    slots = await db.query(
        "equipment_slots",
        [("equipmentId", "==", equipment["id"]), ("date", "==", date_str)],
        limit=100,
    )
    if not slots:
        template = equipment.get("slotTemplate") or DEFAULT_SLOTS
        slots = []
        for i, tpl in enumerate(template):
            slot = {
                "id": f"{equipment['id']}_{date_str}_{i}",
                "equipmentId": equipment["id"],
                "date": date_str,
                "slotName": tpl["slotName"],
                "duration": tpl["duration"],
                "priceRupees": tpl["priceRupees"],
                "recommendedTask": tpl["recommendedTask"],
                "status": "available",
                "bookedByName": None,
            }
            await db.set_doc("equipment_slots", slot["id"], slot)
            slots.append(slot)
    slots.sort(key=lambda s: parse_slot_start(s["slotName"], date_str))
    return slots


async def create_booking_for_user(uid: str, farmer_name: str, slot: dict, equipment: dict, status: str) -> dict:
    booking = {
        "id": f"eqbk_{uuid4().hex[:10]}",
        "userId": uid,
        "slotId": slot["id"],
        "equipmentId": equipment["id"],
        "date": slot["date"],
        "slotName": slot["slotName"],
        "priceRupees": slot["priceRupees"],
        "farmerName": farmer_name,
        "status": status,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    await db.set_doc("equipment_bookings", booking["id"], booking)
    slot["status"] = status
    slot["bookedByName"] = farmer_name
    await db.set_doc("equipment_slots", slot["id"], slot)
    return booking


async def promote_waitlist_head(slot: dict, equipment: dict) -> str | None:
    entries = await db.query("equipment_waitlists", [("slotId", "==", slot["id"])], limit=100)
    if not entries:
        return None
    entries.sort(key=lambda e: e.get("createdAt", ""))
    head = entries[0]
    promoted_uid = head["userId"]
    user = await db.get_doc("users", promoted_uid)
    farmer_name = (user or {}).get("name") or "Farmer"
    status = "booked" if equipment.get("ownerType") == "fpo" else "pending"
    await create_booking_for_user(promoted_uid, farmer_name, slot, equipment, status)
    await db.delete_doc("equipment_waitlists", f"{slot['id']}_{promoted_uid}")
    return promoted_uid


async def notify_equipment_booking(uid: str, title: str, body: str, booking_id: str, type_code: str):
    await send_fcm_to_user(uid, title, body, {"type": type_code, "bookingId": booking_id})
