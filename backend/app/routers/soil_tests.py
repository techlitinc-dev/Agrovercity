from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.core import db
from app.core.deps import require_roles
from app.models.soil_tests import SoilTestBookIn

router = APIRouter(prefix="/soil-tests", tags=["soil-tests"])

ROLES = ("farmer", "farmLandlord")


def _path(uid: str) -> str:
    return f"users/{uid}/soil_tests"


@router.post("/book", status_code=201)
async def book(body: SoilTestBookIn, user: dict = Depends(require_roles(*ROLES))):
    uid = user["id"]
    if body.plotId:
        plot = await db.get_subdoc_at(f"users/{uid}/land_plots", body.plotId)
        if plot is None:
            raise HTTPException(status_code=404, detail={"code": "PLOT_NOT_FOUND", "message": "Plot not found", "fieldErrors": {}})
        existing = await db.list_subdocs(_path(uid))
        if any(b.get("plotId") == body.plotId and b.get("status") != "reportReady" for b in existing):
            raise HTTPException(status_code=409, detail={"code": "SOIL_TEST_ALREADY_BOOKED", "message": "A soil test is already booked for this plot", "fieldErrors": {}})
    booking_id = uuid4().hex
    doc = {
        "id": booking_id,
        **body.model_dump(),
        "status": "booked",
        "resultPdfUrl": None,
        "bookedAt": datetime.now(timezone.utc).isoformat(),
    }
    await db.set_subdoc_at(_path(uid), booking_id, doc)
    return doc


@router.get("")
async def list_bookings(page: int = 1, pageSize: int = 20, user: dict = Depends(require_roles(*ROLES))):
    bookings = await db.list_subdocs(_path(user["id"]))
    bookings.sort(key=lambda b: b.get("bookedAt", ""), reverse=True)
    total = len(bookings)
    page_size = max(1, min(pageSize, 50))
    start = (max(1, page) - 1) * page_size
    return {"data": bookings[start : start + page_size], "page": page, "pageSize": page_size, "total": total}
