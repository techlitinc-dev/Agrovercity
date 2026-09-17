from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.core import db
from app.core.deps import current_user_id
from app.models.ratings import RatingIn, RatingOut

router = APIRouter(prefix="/ratings", tags=["ratings"])

TERMINAL_STATUS = {"transport": "delivered", "vet": "completed", "equipment": "booked"}


def _terminal(kind: str, status: str | None) -> bool:
    return status == TERMINAL_STATUS[kind]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _resolve_booking(kind: str, booking_id: str, uid: str) -> tuple[dict, str | None]:
    if kind == "transport":
        booking = await db.get_doc("transport_bookings", booking_id)
        if booking is None or booking.get("userId") != uid:
            raise HTTPException(status_code=404, detail={"code": "BOOKING_NOT_FOUND", "message": "Booking not found", "fieldErrors": {}})
        vehicle = await db.get_doc("vehicles", booking.get("vehicleId"))
        provider_id = (vehicle or {}).get("ownerId")
    elif kind == "vet":
        booking = await db.get_subdoc_at(f"users/{uid}/vet_bookings", booking_id)
        if booking is None:
            raise HTTPException(status_code=404, detail={"code": "BOOKING_NOT_FOUND", "message": "Booking not found", "fieldErrors": {}})
        provider_id = booking.get("vetId")
    else:
        booking = await db.get_subdoc_at(f"users/{uid}/equipment_bookings", booking_id)
        if booking is None:
            raise HTTPException(status_code=404, detail={"code": "BOOKING_NOT_FOUND", "message": "Booking not found", "fieldErrors": {}})
        equipment = await db.get_doc("equipment", booking.get("equipmentId"))
        provider_id = (equipment or {}).get("ownerId")
    return booking, provider_id


@router.post("", status_code=201)
async def submit_rating(body: RatingIn, uid: str = Depends(current_user_id)):
    booking, provider_id = await _resolve_booking(body.bookingKind, body.bookingId, uid)
    if not _terminal(body.bookingKind, booking.get("status")):
        raise HTTPException(
            status_code=409,
            detail={"code": "NOT_COMPLETED", "message": "पूरी न हुई बुकिंग रेट नहीं की जा सकती", "fieldErrors": {}},
        )
    existing = await db.query(
        "ratings",
        [("bookingId", "==", body.bookingId), ("bookingKind", "==", body.bookingKind)],
        limit=1,
    )
    if existing:
        raise HTTPException(status_code=409, detail={"code": "ALREADY_RATED", "message": "आप पहले ही रेटिंग दे चुके हैं", "fieldErrors": {}})

    rating_id = uuid4().hex
    doc = {
        "id": rating_id,
        "bookingKind": body.bookingKind,
        "bookingId": body.bookingId,
        "stars": body.stars,
        "comment": body.comment,
        "raterId": uid,
        "providerId": provider_id,
        "createdAt": _now_iso(),
    }
    await db.set_doc("ratings", rating_id, doc)

    if provider_id:
        all_ratings = await db.query("ratings", [("providerId", "==", provider_id)], limit=1000)
        count = len(all_ratings)
        avg = round(sum(r.get("stars", 0) for r in all_ratings) / count, 1) if count else None
        await db.set_doc("provider_ratings", provider_id, {"ratingCount": count, "ratingAvg": avg, "updatedAt": _now_iso()})

    return RatingOut(**doc)


@router.get("/providers/{provider_id}")
async def provider_rating(provider_id: str, uid: str = Depends(current_user_id)):
    agg = await db.get_doc("provider_ratings", provider_id)
    if agg is None:
        return {"ratingAvg": None, "ratingCount": 0}
    return {"ratingAvg": agg.get("ratingAvg"), "ratingCount": agg.get("ratingCount", 0)}
