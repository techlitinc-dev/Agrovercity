import zlib

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.deps import require_roles

router = APIRouter(prefix="/water", tags=["water"])

GROUNDWATER = {
    "Nashik": {"depthMeters": 18.5, "zone": "semiCritical"},
    "Pune": {"depthMeters": 12.0, "zone": "safe"},
    "Nagpur": {"depthMeters": 25.2, "zone": "critical"},
    "Aurangabad": {"depthMeters": 21.0, "zone": "semiCritical"},
}


class PmksyIn(BaseModel):
    acres: float = Field(gt=0)


@router.get("/schedule")
async def schedule(user: dict = Depends(require_roles("farmer"))):
    uid = user["id"]
    method = user.get("irrigationType") or "drip"
    entries = []
    for crop in user.get("activeCrops", []):
        moisture = 35 + (zlib.crc32((uid + crop).encode()) % 40)
        entries.append(
            {
                "plotName": crop,
                "moisturePercent": moisture,
                "recommendedMinutes": 90 if moisture < 60 else 30,
                "method": method,
            }
        )
    return {"data": entries, "page": 1, "pageSize": 50, "total": len(entries)}


@router.get("/groundwater")
async def groundwater(district: str | None = None, user: dict = Depends(require_roles("farmer"))):
    if not district:
        raise HTTPException(status_code=400, detail={"code": "MISSING_DISTRICT", "message": "district is required", "fieldErrors": {}})
    info = GROUNDWATER.get(district, {"depthMeters": 15.0, "zone": "safe"})
    return {**info, "measuredAt": datetime.now().date().isoformat()}


@router.get("/canal-rotation")
async def canal_rotation(canal: str | None = None, user: dict = Depends(require_roles("farmer"))):
    today = datetime.now().date()
    next_monday = today + timedelta(days=(0 - today.weekday()) % 7 or 7)
    next_thursday = today + timedelta(days=(3 - today.weekday()) % 7 or 7)
    rotations = [
        {"canalName": "Gangapur Canal", "nextDate": next_monday.isoformat(), "slotTime": "06:00-12:00"},
        {"canalName": "Palkhed Canal", "nextDate": next_thursday.isoformat(), "slotTime": "12:00-18:00"},
    ]
    if canal:
        c = canal.lower()
        rotations = [r for r in rotations if c in r["canalName"].lower()]
    return {"data": rotations, "page": 1, "pageSize": 50, "total": len(rotations)}


@router.post("/pmksy-calculator")
async def pmksy_calculator(body: PmksyIn, user: dict = Depends(require_roles("farmer"))):
    total_cost = body.acres * 85000
    subsidy_percent = 55
    subsidy_amount = round(total_cost * 0.55, 2)
    farmer_share = round(total_cost - subsidy_amount, 2)
    return {
        "totalCost": total_cost,
        "subsidyPercent": subsidy_percent,
        "subsidyAmount": subsidy_amount,
        "farmerShare": farmer_share,
    }
