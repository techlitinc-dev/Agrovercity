import re

from fastapi import APIRouter, Depends, HTTPException

from app.core import db
from app.core.deps import require_roles
from app.services.land_records import get_adapter

router = APIRouter(prefix="/land-records", tags=["land-records"])

ROLES = ("farmer", "farmLandlord")


@router.get("/search")
async def search(gatNumber: str | None = None, village: str | None = None, district: str | None = None, type: str = "712", user: dict = Depends(require_roles(*ROLES))):
    if type not in {"712", "8A"}:
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "type must be 712 or 8A", "fieldErrors": {"type": "must be 712 or 8A"}})
    if gatNumber is None and village is None:
        raise HTTPException(status_code=400, detail={"code": "MISSING_SEARCH_PARAM", "message": "Provide gatNumber or village", "fieldErrors": {}})
    if gatNumber is not None and not re.fullmatch(r"[A-Za-z0-9]{1,20}", gatNumber):
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "Invalid gatNumber", "fieldErrors": {"gatNumber": "must be alphanumeric, max 20"}})
    if village is not None and len(village) < 3:
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "village too short", "fieldErrors": {"village": "min 3 characters"}})
    records = get_adapter().search(gatNumber, village, district, type)
    data = [r.model_dump() for r in records]
    total = len(data)
    page_size = 50
    return {"data": data[:page_size], "page": 1, "pageSize": page_size, "total": total}


@router.get("/{record_id}/pdf")
async def record_pdf(record_id: str, user: dict = Depends(require_roles(*ROLES))):
    record = get_adapter().get_by_id(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail={"code": "RECORD_NOT_FOUND", "message": "Record not found", "fieldErrors": {}})
    return {"pdfUrl": get_adapter().get_pdf_url(record_id)}


@router.post("/{record_id}/import")
async def import_record(record_id: str, user: dict = Depends(require_roles(*ROLES))):
    record = get_adapter().get_by_id(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail={"code": "RECORD_NOT_FOUND", "message": "Record not found", "fieldErrors": {}})
    uid = user["id"]
    user_doc = await db.get_doc("users", uid)
    if user_doc is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "User not found", "fieldErrors": {}})
    user_doc["landAreaAcres"] = record.totalAreaAcres
    land_records = list(user_doc.get("landRecords", []))
    land_records.append(
        {
            "gatNumber": record.gatNumber,
            "village": record.village,
            "ownerName": record.ownerName,
            "cropHistory": record.cropHistory,
        }
    )
    user_doc["landRecords"] = land_records
    await db.set_doc("users", uid, user_doc)
    return {"imported": True, "landAreaAcres": record.totalAreaAcres}
