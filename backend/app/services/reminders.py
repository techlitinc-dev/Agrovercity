"""Equipment booking reminders (30-min window) — X4 SMS hook."""

from datetime import datetime, timedelta, timezone

from app.core import db
from app.services import sms as sms_service
from app.services.equipment import IST, parse_slot_start


def _now_ist(now: datetime | None = None) -> datetime:
    return now or datetime.now(IST)


async def scan_and_send(now: datetime | None = None) -> dict:
    now = _now_ist(now)
    reminded = 0
    bookings = await db.list_collection_group("equipment_bookings")
    for entry in bookings:
        booking = entry["doc"]
        if booking.get("status") != "booked" or booking.get("reminderSentAt"):
            continue
        try:
            start = parse_slot_start(booking.get("slotName", ""), booking.get("date", ""))
        except ValueError:
            continue
        delta = start - now
        if not timedelta(0) <= delta <= timedelta(minutes=30):
            continue
        if entry["path"]:
            farmer_uid = entry["path"].split("/")[1]
        else:
            farmer_uid = booking.get("userId")
        farmer = await db.get_doc("users", farmer_uid) if farmer_uid else None
        phone = (farmer or {}).get("phone")
        equipment = await db.get_doc("equipment", booking.get("equipmentId"))
        if phone:
            await sms_service.get_sms_sender().send(
                phone,
                "equipment_reminder",
                {"equipment": (equipment or {}).get("name", ""), "slot": booking.get("slotName", "")},
            )
        booking["reminderSentAt"] = datetime.now(timezone.utc).isoformat()
        if entry["path"]:
            await db.set_subdoc_at(f"{entry['path']}/equipment_bookings", entry["doc_id"], booking)
        else:
            await db.set_doc("equipment_bookings", entry["doc_id"], booking)
        reminded += 1
    return {"reminded": reminded}
