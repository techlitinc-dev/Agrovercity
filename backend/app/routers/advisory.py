from fastapi import APIRouter, Depends, File, UploadFile

from app.core import db
from app.core.deps import require_roles
from app.models.advisory import NpkIn, NpkOut, SaturationIn
from app.services import advisory as advisory_service
from app.services.disease_model import get_disease_adapter
from app.services.storage import upload_user_file, validate_upload

router = APIRouter(prefix="/advisory", tags=["advisory"])


@router.post("/saturation")
async def saturation(body: SaturationIn, user: dict = Depends(require_roles("farmer"))):
    uid = user["id"]
    if body.shareSowingIntent:
        season = advisory_service.current_season()
        doc_id = f"{uid}_{body.crop}_{season}"
        await db.set_doc(
            "crop_cycles",
            doc_id,
            {
                "id": doc_id,
                "userId": uid,
                "crop": body.crop,
                "district": body.district,
                "lat": body.lat,
                "lng": body.lng,
                "season": season,
                "createdAt": datetime_now_iso(),
            },
        )
    return await advisory_service.saturation(body, exclude_uid=uid)


def datetime_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


@router.post("/disease-scan")
async def disease_scan(file: UploadFile = File(...), user: dict = Depends(require_roles("farmer"))):
    data = await file.read()
    validate_upload(file.content_type, len(data))
    uid = user["id"]
    upload_user_file(uid, data, file.filename or "scan.jpg", file.content_type, prefix="scans")
    results = await get_disease_adapter().scan(data)
    return {"results": [r.model_dump() for r in results]}


@router.get("/pest-radar")
async def pest_radar(lat: float | None = None, lng: float | None = None, radiusKm: int = 5, user: dict = Depends(require_roles("farmer"))):
    today = datetime_today()
    alerts = [
        {"disease": "Pink bollworm", "crop": "Cotton", "distanceKm": 3.2, "riskLevel": "yellow", "reportedAt": today},
        {"disease": "Leaf curl", "crop": "Chilli", "distanceKm": 4.8, "riskLevel": "green", "reportedAt": today},
    ]
    return {"data": alerts, "page": 1, "pageSize": 50, "total": len(alerts)}


def datetime_today() -> str:
    from datetime import date

    return date.today().isoformat()


@router.post("/npk")
async def npk(body: NpkIn, user: dict = Depends(require_roles("farmer"))):
    result = advisory_service.npk_recommendation(body.n, body.p, body.k, body.crop)
    return NpkOut(**result)
