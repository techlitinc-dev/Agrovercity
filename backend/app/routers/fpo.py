from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException

from app.core import db
from app.core.deps import require_roles
from app.models.equipment import JoinPoolRequest
from app.services import equipment as equipment_service

router = APIRouter(prefix="/fpo", tags=["fpo"])

FARMER_ROLE = ("farmer",)


def _now_iso() -> str:
    return datetime.now(equipment_service.IST).isoformat()


@router.get("/me")
async def fpo_me(user: dict = Depends(require_roles(*FARMER_ROLE))):
    docs = await db.query("fpos", [], limit=1)
    if not docs:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "No FPO configured", "fieldErrors": {}},
        )
    return docs[0]


@router.get("/pools")
async def list_pools(user: dict = Depends(require_roles(*FARMER_ROLE))):
    docs = await db.query("fpo_pools", [], limit=1000)
    return {"data": docs}


@router.post("/pools/{pool_id}/join")
async def join_pool(pool_id: str, body: JoinPoolRequest, user: dict = Depends(require_roles(*FARMER_ROLE))):
    if body.units < 1:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "units must be >= 1", "fieldErrors": {"units": "must be >= 1"}},
        )
    pool = await db.get_doc("fpo_pools", pool_id)
    if pool is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "POOL_NOT_FOUND", "message": "Pool not found", "fieldErrors": {}},
        )
    if pool.get("bookedUnits", 0) + body.units > pool.get("targetUnits", 0):
        raise HTTPException(
            status_code=409,
            detail={"code": "POOL_FULL", "message": "Pool target already met", "fieldErrors": {}},
        )
    pool["bookedUnits"] = pool.get("bookedUnits", 0) + body.units
    await db.set_doc("fpo_pools", pool_id, pool)
    await db.set_subdoc("fpo_pools", pool_id, "members", user["id"], {"units": body.units, "joinedAt": _now_iso()})
    return pool


@router.get("/machinery")
async def machinery(week: str | None = None, user: dict = Depends(require_roles(*FARMER_ROLE))):
    iso_year, iso_week, _ = equipment_service.today_ist().isocalendar()
    week_str = week or f"{iso_year}-W{iso_week:02d}"
    try:
        monday = datetime.strptime(f"{week_str}-1", "%G-W%V-%u").date()
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "week must be ISO format YYYY-Www", "fieldErrors": {"week": "must be ISO format YYYY-Www"}},
        )
    week_dates = [(monday + timedelta(days=i)).isoformat() for i in range(7)]
    machines = await db.query("equipment", [("ownerType", "==", "fpo")], limit=1000)
    machines = [m for m in machines if m.get("active", True) and m.get("docStatus") == "verified"]
    data = []
    for machine in machines:
        days = {}
        for date_str in week_dates:
            slots = await equipment_service.get_or_generate_slots(machine, date_str)
            days[date_str] = slots
        data.append({"equipmentId": machine["id"], "name": machine.get("name"), "days": days})
    return {"data": data}
