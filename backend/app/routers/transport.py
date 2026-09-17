from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.core import db
from app.core.deps import require_roles
from app.models.transport import (
    AcceptBookingRequest,
    AvailabilityRequest,
    CreateBookingRequest,
    FareEstimateRequest,
    OwnerVehicleRequest,
    RejectBookingRequest,
    UpdateBookingRequest,
)
from app.services.notifications import send_fcm_to_user

router = APIRouter(prefix="/transport", tags=["transport"])

BOOKER_ROLES = ("farmer", "seller")
TRANSPORT_ROLE = ("transport",)
FAREROLE_ROLES = ("farmer", "seller", "transport")

VEHICLE_TYPES = [
    {"type": "Tata Ace", "baseFare": 500, "perKmRate": 35, "capacityTonnes": 0.75},
    {"type": "Bolero Maxi", "baseFare": 800, "perKmRate": 45, "capacityTonnes": 1.5},
    {"type": "Tractor Trolley", "baseFare": 1000, "perKmRate": 30, "capacityTonnes": 3.0},
]

TRANSITIONS = {
    "requested": {"accepted", "cancelled"},
    "accepted": {"enRoute", "cancelled"},
    "enRoute": {"delivered"},
    "delivered": set(),
    "cancelled": set(),
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _vehicle_type_or_422(vehicle_type: str) -> dict:
    for vt in VEHICLE_TYPES:
        if vt["type"] == vehicle_type:
            return vt
    raise HTTPException(
        status_code=422,
        detail={"code": "UNKNOWN_VEHICLE_TYPE", "message": "Unknown vehicle type", "fieldErrors": {"vehicleType": "must be one of Tata Ace, Bolero Maxi, Tractor Trolley"}},
    )


def _fare(vt: dict, distance_km: float) -> dict:
    distance_fare = vt["perKmRate"] * distance_km
    return {"baseFare": vt["baseFare"], "distanceFare": distance_fare, "totalFare": vt["baseFare"] + distance_fare}


async def _check_assignable_vehicle(user: dict, vehicle_id: str) -> dict:
    vehicle = await db.get_doc("vehicles", vehicle_id)
    if vehicle is None or vehicle.get("ownerId") != user["id"]:
        raise HTTPException(
            status_code=403,
            detail={"code": "NOT_VEHICLE_OWNER", "message": "Vehicle does not belong to this transporter", "fieldErrors": {}},
        )
    if vehicle.get("docStatus") != "verified":
        raise HTTPException(
            status_code=422,
            detail={"code": "VEHICLE_NOT_VERIFIED", "message": "Vehicle documents are not verified", "fieldErrors": {"vehicleId": "vehicle documents pending verification"}},
        )
    return vehicle


@router.get("/vehicles")
async def list_vehicle_types(user: dict = Depends(require_roles(*FAREROLE_ROLES))):
    return {"data": VEHICLE_TYPES}


@router.post("/fare-estimate")
async def fare_estimate(body: FareEstimateRequest, user: dict = Depends(require_roles(*FAREROLE_ROLES))):
    vt = _vehicle_type_or_422(body.vehicleType)
    return _fare(vt, body.distanceKm)


@router.post("/bookings")
async def create_booking(body: CreateBookingRequest, user: dict = Depends(require_roles(*BOOKER_ROLES))):
    if body.lotId:
        lot = await db.get_doc("market_lots", body.lotId)
        if lot is None or lot.get("farmerId") != user["id"]:
            raise HTTPException(
                status_code=404,
                detail={"code": "LOT_NOT_FOUND", "message": "Lot not found", "fieldErrors": {}},
            )
        if lot.get("status") != "open":
            raise HTTPException(
                status_code=409,
                detail={"code": "LOT_NOT_OPEN", "message": "Lot is not open for pickup", "fieldErrors": {}},
            )
    vt = _vehicle_type_or_422(body.vehicleType)
    fare = _fare(vt, body.distanceKm)
    booking_id = f"bk_{uuid4().hex[:10]}"
    booking = {
        "id": booking_id,
        "userId": user["id"],
        "vehicleType": body.vehicleType,
        "distanceKm": body.distanceKm,
        "pickup": body.pickup,
        "drop": body.drop,
        "date": body.date,
        "fare": fare["totalFare"],
        "status": "requested",
        "vehicleId": None,
        "vehicleNo": None,
        "lotId": body.lotId,
        "createdAt": _now_iso(),
    }
    await db.set_doc("transport_bookings", booking_id, booking)
    return booking


@router.get("/bookings")
async def list_bookings(status: str | None = None, page: int = 1, pageSize: int = 20, user: dict = Depends(require_roles(*TRANSPORT_ROLE))):
    my_vehicle_ids = {d["id"] for d in await db.query("vehicles", [("ownerId", "==", user["id"])], limit=1000)}
    docs = await db.query("transport_bookings", [], limit=1000)
    docs = [d for d in docs if d.get("status") == "requested" or d.get("vehicleId") in my_vehicle_ids]
    if status:
        docs = [d for d in docs if d.get("status") == status]
    for d in docs:
        d["lot"] = await _lot_summary(d.get("lotId"))
    total = len(docs)
    page_size = max(1, min(pageSize, 50))
    start = (max(1, page) - 1) * page_size
    return {"data": docs[start : start + page_size], "page": page, "pageSize": page_size, "total": total}


async def _lot_summary(lot_id: str | None) -> dict | None:
    if not lot_id:
        return None
    lot = await db.get_doc("market_lots", lot_id)
    if lot is None:
        return None
    return {"crop": lot.get("crop"), "quantityQuintals": lot.get("quantityQuintals"), "expectedRate": lot.get("expectedRate")}


async def _get_booking_or_404(booking_id: str) -> dict:
    booking = await db.get_doc("transport_bookings", booking_id)
    if booking is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "BOOKING_NOT_FOUND", "message": "Booking not found", "fieldErrors": {}},
        )
    return booking


# PATCH /bookings kept for existing clients — POST accept/reject are the canonical paths now.
@router.patch("/bookings/{booking_id}")
async def update_booking(booking_id: str, body: UpdateBookingRequest, user: dict = Depends(require_roles(*TRANSPORT_ROLE))):
    booking = await _get_booking_or_404(booking_id)
    if body.status not in TRANSITIONS.get(booking.get("status"), set()):
        raise HTTPException(
            status_code=409,
            detail={"code": "ILLEGAL_TRANSITION", "message": f"Cannot move booking from {booking.get('status')} to {body.status}", "fieldErrors": {}},
        )
    if body.status == "accepted" and body.vehicleId:
        await _check_assignable_vehicle(user, body.vehicleId)
        booking["vehicleId"] = body.vehicleId
        if body.vehicleNo:
            booking["vehicleNo"] = body.vehicleNo
    if body.status == "delivered":
        _require_pod(body)
        booking["pod"] = {"photos": body.podPhotos, "receiverName": body.receiverName, "deliveredAt": _now_iso()}
    booking["status"] = body.status
    await db.set_doc("transport_bookings", booking_id, booking)
    return booking


def _require_pod(body: UpdateBookingRequest):
    missing = {}
    if not body.podPhotos:
        missing["podPhotos"] = "at least one photo URL is required"
    if body.receiverName is None or not body.receiverName.strip():
        missing["receiverName"] = "receiver name is required"
    if missing:
        raise HTTPException(
            status_code=422,
            detail={"code": "POD_REQUIRED", "message": "Proof of delivery is required", "fieldErrors": missing},
        )


@router.post("/bookings/{booking_id}/accept")
async def accept_booking(booking_id: str, body: AcceptBookingRequest, user: dict = Depends(require_roles(*TRANSPORT_ROLE))):
    booking = await _get_booking_or_404(booking_id)
    if booking.get("status") != "requested":
        raise HTTPException(
            status_code=409,
            detail={"code": "ILLEGAL_TRANSITION", "message": f"Cannot accept a booking in status {booking.get('status')}", "fieldErrors": {}},
        )
    if body.vehicleId:
        vehicle = await _check_assignable_vehicle(user, body.vehicleId)
        booking["vehicleId"] = body.vehicleId
        booking["vehicleNo"] = body.vehicleNo or vehicle.get("registrationNo")
    booking["status"] = "accepted"
    await db.set_doc("transport_bookings", booking_id, booking)
    await send_fcm_to_user(
        booking["userId"],
        "बुकिंग स्वीकृत",
        f"{booking.get('vehicleNo') or 'वाहन'} आपकी बुकिंग स्वीकार कर रहा है",
        {"type": "booking_accepted", "bookingId": booking_id},
    )
    return booking


@router.post("/bookings/{booking_id}/reject")
async def reject_booking(booking_id: str, body: RejectBookingRequest, user: dict = Depends(require_roles(*TRANSPORT_ROLE))):
    if body.reason is None or len(body.reason.strip()) < 3:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "reason must be at least 3 characters", "fieldErrors": {"reason": "must be at least 3 characters"}},
        )
    booking = await _get_booking_or_404(booking_id)
    if booking.get("status") != "requested":
        raise HTTPException(
            status_code=409,
            detail={"code": "ILLEGAL_TRANSITION", "message": f"Cannot reject a booking in status {booking.get('status')}", "fieldErrors": {}},
        )
    booking["status"] = "cancelled"
    booking["cancellationReason"] = body.reason
    booking["cancelledBy"] = "transporter"
    await db.set_doc("transport_bookings", booking_id, booking)
    await send_fcm_to_user(
        booking["userId"],
        "बुकिंग अस्वीकृत",
        f"आपकी बुकिंग अस्वीकृत: {body.reason}",
        {"type": "booking_rejected", "bookingId": booking_id},
    )
    return booking


@router.post("/vehicles")
async def create_vehicle(body: OwnerVehicleRequest, user: dict = Depends(require_roles(*TRANSPORT_ROLE))):
    vehicle_id = f"veh_{uuid4().hex[:10]}"
    vehicle = {
        "id": vehicle_id,
        "ownerId": user["id"],
        **body.model_dump(),
        # Admin verify/reject action lives in the admin KYC queue (Day 14, item A1).
        "docStatus": "pending",
        "rejectionReason": None,
        "active": True,
        "availableDates": [],
        "createdAt": _now_iso(),
    }
    await db.set_doc("vehicles", vehicle_id, vehicle)
    return vehicle


@router.get("/vehicles/my")
async def my_vehicles(verifiedOnly: bool = False, user: dict = Depends(require_roles(*TRANSPORT_ROLE))):
    docs = await db.query("vehicles", [("ownerId", "==", user["id"])], limit=1000)
    if verifiedOnly:
        docs = [d for d in docs if d.get("docStatus") == "verified"]
    return {"data": docs}


@router.put("/vehicles/{vehicle_id}")
async def update_vehicle(vehicle_id: str, body: OwnerVehicleRequest, user: dict = Depends(require_roles(*TRANSPORT_ROLE))):
    vehicle = await _get_own_vehicle_or_403(vehicle_id, user)
    vehicle.update(body.model_dump())
    await db.set_doc("vehicles", vehicle_id, vehicle)
    return vehicle


@router.delete("/vehicles/{vehicle_id}")
async def delete_vehicle(vehicle_id: str, user: dict = Depends(require_roles(*TRANSPORT_ROLE))):
    vehicle = await _get_own_vehicle_or_403(vehicle_id, user)
    vehicle["active"] = False
    await db.set_doc("vehicles", vehicle_id, vehicle)
    return {"ok": True, "active": False}


@router.get("/vehicles/{vehicle_id}/calendar")
async def vehicle_calendar(vehicle_id: str, user: dict = Depends(require_roles(*TRANSPORT_ROLE))):
    await _get_own_vehicle_or_403(vehicle_id, user)
    docs = await db.query("transport_bookings", [], limit=1000)
    bookings = [
        {"bookingId": d["id"], "date": d.get("date"), "status": d.get("status"), "pickup": d.get("pickup"), "drop": d.get("drop")}
        for d in docs
        if d.get("vehicleId") == vehicle_id and d.get("status") in {"accepted", "enRoute"}
    ]
    return {"vehicleId": vehicle_id, "bookings": bookings}


@router.put("/vehicles/{vehicle_id}/availability")
async def set_availability(vehicle_id: str, body: AvailabilityRequest, user: dict = Depends(require_roles(*TRANSPORT_ROLE))):
    vehicle = await _get_own_vehicle_or_403(vehicle_id, user)
    vehicle["availableDates"] = body.availableDates
    await db.set_doc("vehicles", vehicle_id, vehicle)
    return vehicle


async def _get_own_vehicle_or_403(vehicle_id: str, user: dict) -> dict:
    vehicle = await db.get_doc("vehicles", vehicle_id)
    if vehicle is None or vehicle.get("ownerId") != user["id"]:
        raise HTTPException(
            status_code=403,
            detail={"code": "NOT_VEHICLE_OWNER", "message": "Vehicle does not belong to this transporter", "fieldErrors": {}},
        )
    return vehicle
