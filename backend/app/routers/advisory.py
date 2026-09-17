from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.core import db
from app.core.deps import require_roles
from app.models.advisory import NpkIn, NpkOut, SaturationIn
from app.services import advisory as advisory_service
from app.services.disease_model import get_disease_adapter
from app.services.storage import upload_user_file, validate_upload


class SowingIntentIn(BaseModel):
    crop: str
    plotId: str | None = None
    plannedDate: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")

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


@router.post("/sowing-intent", status_code=201)
async def sowing_intent(body: SowingIntentIn, user: dict = Depends(require_roles("farmer"))):
    from app.services.consents import ConsentRequiredError, require_data_sharing

    uid = user["id"]
    try:
        await require_data_sharing(uid)
    except ConsentRequiredError:
        raise HTTPException(
            status_code=403,
            detail={"code": "CONSENT_REQUIRED", "message": "डेटा साझाकरण की सहमति आवश्यक है", "fieldErrors": {}},
        )
    if body.plotId:
        plot = await db.get_subdoc_at(f"users/{uid}/land_plots", body.plotId)
        if plot is None:
            raise HTTPException(status_code=404, detail={"code": "PLOT_NOT_FOUND", "message": "Plot not found", "fieldErrors": {}})
    if body.plannedDate < date.today().isoformat():
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "plannedDate cannot be in the past", "fieldErrors": {"plannedDate": "cannot be in the past"}},
        )
    season = advisory_service.current_season()
    doc_id = f"{uid}_{body.crop}_{season}"
    await db.set_doc(
        "crop_cycles",
        doc_id,
        {
            "id": doc_id,
            "userId": uid,
            "crop": body.crop,
            "plotId": body.plotId,
            "district": user.get("district", ""),
            "lat": user.get("farmBoundaryPoints", [{}])[0].get("lat") if user.get("farmBoundaryPoints") else None,
            "lng": user.get("farmBoundaryPoints", [{}])[0].get("lng") if user.get("farmBoundaryPoints") else None,
            "season": season,
            "plannedDate": body.plannedDate,
            "isIntent": True,
            "createdAt": datetime_now_iso(),
        },
    )
    return {"recorded": True, "isIntent": True}


@router.post("/npk")
async def npk(body: NpkIn, user: dict = Depends(require_roles("farmer"))):
    result = advisory_service.npk_recommendation(body.n, body.p, body.k, body.crop)
    return NpkOut(**result)
