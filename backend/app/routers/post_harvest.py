from datetime import date, datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.core import db
from app.core.deps import require_roles
from app.data.cold_storage_seed import seed_cold_storage
from app.services.grading_model import get_grading_adapter
from app.services.storage import upload_user_file, validate_upload

router = APIRouter(prefix="/post-harvest", tags=["post-harvest"])

STORAGE_ROLE = ("farmer", "transport", "seller")
GRADE_ROLE = ("farmer", "seller")


class ColdStorageBookIn(BaseModel):
    quantityQuintals: float = Field(gt=0)
    fromDate: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    months: int = Field(ge=1, le=12)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/cold-storage")
async def cold_storage(lat: float | None = None, lng: float | None = None, page: int = 1, pageSize: int = 20, user: dict = Depends(require_roles(*STORAGE_ROLE))):
    await seed_cold_storage()
    docs = await db.query("cold_storage", [], limit=1000)
    docs.sort(key=lambda d: d.get("distanceKm", 0))
    for d in docs:
        d["availableMT"] = round(d.get("availableMT", 0) - d.get("bookedQuintals", 0) / 10, 1)
    total = len(docs)
    page_size = max(1, min(pageSize, 50))
    start = (max(1, page) - 1) * page_size
    return {"data": docs[start : start + page_size], "page": page, "pageSize": page_size, "total": total}


@router.post("/cold-storage/{facility_id}/book", status_code=201)
async def book_cold_storage(facility_id: str, body: ColdStorageBookIn, user: dict = Depends(require_roles("farmer"))):
    facility = await db.get_doc("cold_storage", facility_id)
    if facility is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "STORAGE_NOT_FOUND", "message": "Cold storage not found", "fieldErrors": {}},
        )
    if body.fromDate < date.today().isoformat():
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "fromDate cannot be in the past", "fieldErrors": {"fromDate": "cannot be in the past"}},
        )
    available = facility.get("availableMT", 0) * 10 - facility.get("bookedQuintals", 0)
    if body.quantityQuintals > available:
        raise HTTPException(
            status_code=409,
            detail={"code": "INSUFFICIENT_CAPACITY", "message": "इतनी क्षमता उपलब्ध नहीं", "fieldErrors": {}},
        )
    facility["bookedQuintals"] = facility.get("bookedQuintals", 0) + body.quantityQuintals
    await db.set_doc("cold_storage", facility_id, facility)
    booking_id = uuid4().hex
    doc = {
        "id": booking_id,
        "facilityId": facility_id,
        "facilityName": facility.get("name"),
        "quantityQuintals": body.quantityQuintals,
        "fromDate": body.fromDate,
        "months": body.months,
        "status": "booked",
        "bookedAt": _now_iso(),
    }
    await db.set_subdoc_at(f"users/{user['id']}/cold_storage_bookings", booking_id, doc)
    return doc


@router.post("/grade")
async def grade(images: list[UploadFile] = File(...), user: dict = Depends(require_roles(*GRADE_ROLE))):
    if not 1 <= len(images) <= 3:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "Upload 1–3 images", "fieldErrors": {"images": "1–3 images required"}},
        )
    uid = user["id"]
    for image in images:
        data = await image.read()
        validate_upload(image.content_type, len(data))
        upload_user_file(uid, data, image.filename or "produce.jpg", image.content_type, prefix="grading")
    return get_grading_adapter().scan(b"")
