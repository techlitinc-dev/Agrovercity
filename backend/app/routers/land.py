from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response

from app.core import db
from app.core.deps import current_user_id
from app.models.land import LeaseIn, LeaseUpdateRequest, PlotIn, RentPaymentIn
from app.services import land as land_service

router = APIRouter(prefix="/land", tags=["land"])

ROLES = ("farmer", "farmLandlord")


def _envelope(data: list[dict], page: int, page_size: int) -> dict:
    total = len(data)
    start = (max(1, page) - 1) * page_size
    return {"data": data[start : start + page_size], "page": page, "pageSize": page_size, "total": total}


def _page_size(pageSize: int) -> int:
    return max(1, min(pageSize, 50))


@router.get("/plots")
async def list_plots(page: int = 1, pageSize: int = 20, uid: str = Depends(current_user_id)):
    await land_service.user_or_403(uid, *ROLES)
    return _envelope(await db.list_subdocs(land_service.plots_path(uid)), page, _page_size(pageSize))


@router.post("/plots", status_code=201)
async def create_plot(body: PlotIn, uid: str = Depends(current_user_id)):
    await land_service.user_or_403(uid, *ROLES)
    plot_id = f"plot_{uuid4().hex[:10]}"
    doc = {"id": plot_id, **body.model_dump(), "status": "vacant", "createdAt": datetime.utcnow().isoformat()}
    await db.set_subdoc_at(land_service.plots_path(uid), plot_id, doc)
    return doc


@router.put("/plots/{plot_id}")
async def update_plot(plot_id: str, body: PlotIn, uid: str = Depends(current_user_id)):
    await land_service.user_or_403(uid, *ROLES)
    plot = await db.get_subdoc_at(land_service.plots_path(uid), plot_id)
    if plot is None:
        raise HTTPException(status_code=404, detail={"code": "PLOT_NOT_FOUND", "message": "Plot not found", "fieldErrors": {}})
    plot.update(body.model_dump(exclude_unset=True))
    await db.set_subdoc_at(land_service.plots_path(uid), plot_id, plot)
    return plot


@router.delete("/plots/{plot_id}", status_code=204)
async def delete_plot(plot_id: str, uid: str = Depends(current_user_id)):
    await land_service.user_or_403(uid, *ROLES)
    plot = await db.get_subdoc_at(land_service.plots_path(uid), plot_id)
    if plot is None:
        raise HTTPException(status_code=404, detail={"code": "PLOT_NOT_FOUND", "message": "Plot not found", "fieldErrors": {}})
    leases = await db.list_subdocs(land_service.leases_path(uid))
    if any(l.get("plotId") == plot_id and l.get("status") == "active" for l in leases):
        raise HTTPException(status_code=409, detail={"code": "PLOT_HAS_ACTIVE_LEASE", "message": "Plot has an active lease", "fieldErrors": {}})
    await db.delete_subdoc_at(land_service.plots_path(uid), plot_id)
    return Response(status_code=204)


@router.get("/leases")
async def list_leases(status: str | None = None, page: int = 1, pageSize: int = 20, uid: str = Depends(current_user_id)):
    await land_service.user_or_403(uid, *ROLES)
    leases = await db.list_subdocs(land_service.leases_path(uid))
    if status:
        leases = [l for l in leases if l.get("status") == status]
    return _envelope(leases, page, _page_size(pageSize))


@router.post("/leases", status_code=201)
async def create_lease(body: LeaseIn, uid: str = Depends(current_user_id)):
    await land_service.user_or_403(uid, *ROLES)
    plot = await db.get_subdoc_at(land_service.plots_path(uid), body.plotId)
    if plot is None:
        raise HTTPException(status_code=404, detail={"code": "PLOT_NOT_FOUND", "message": "Plot not found", "fieldErrors": {}})
    if body.endDate <= body.startDate:
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "endDate must be after startDate", "fieldErrors": {"endDate": "must be after startDate"}})
    lease_id = f"lease_{uuid4().hex[:10]}"
    doc = {"id": lease_id, **body.model_dump(), "status": "active", "verified": False, "createdAt": datetime.utcnow().isoformat()}
    await db.set_subdoc_at(land_service.leases_path(uid), lease_id, doc)
    plot["status"] = "leased"
    await db.set_subdoc_at(land_service.plots_path(uid), body.plotId, plot)
    return doc


@router.put("/leases/{lease_id}")
async def update_lease(lease_id: str, body: LeaseUpdateRequest, uid: str = Depends(current_user_id)):
    await land_service.user_or_403(uid, *ROLES)
    lease = await db.get_subdoc_at(land_service.leases_path(uid), lease_id)
    if lease is None:
        raise HTTPException(status_code=404, detail={"code": "LEASE_NOT_FOUND", "message": "Lease not found", "fieldErrors": {}})
    updates = body.model_dump(exclude_unset=True)
    lease.update(updates)
    await db.set_subdoc_at(land_service.leases_path(uid), lease_id, lease)
    if updates.get("status") == "ended":
        plot = await db.get_subdoc_at(land_service.plots_path(uid), lease["plotId"])
        if plot is not None:
            plot["status"] = "vacant"
            await db.set_subdoc_at(land_service.plots_path(uid), lease["plotId"], plot)
    return lease


@router.delete("/leases/{lease_id}", status_code=204)
async def delete_lease(lease_id: str, uid: str = Depends(current_user_id)):
    await land_service.user_or_403(uid, *ROLES)
    lease = await db.get_subdoc_at(land_service.leases_path(uid), lease_id)
    if lease is None:
        raise HTTPException(status_code=404, detail={"code": "LEASE_NOT_FOUND", "message": "Lease not found", "fieldErrors": {}})
    await db.delete_subdoc_at(land_service.leases_path(uid), lease_id)
    if lease.get("status") == "active":
        plot = await db.get_subdoc_at(land_service.plots_path(uid), lease["plotId"])
        if plot is not None:
            plot["status"] = "vacant"
            await db.set_subdoc_at(land_service.plots_path(uid), lease["plotId"], plot)
    return Response(status_code=204)


@router.post("/leases/{lease_id}/payments", status_code=201)
async def add_payment(lease_id: str, body: RentPaymentIn, uid: str = Depends(current_user_id)):
    await land_service.user_or_403(uid, *ROLES)
    lease = await db.get_subdoc_at(land_service.leases_path(uid), lease_id)
    if lease is None:
        raise HTTPException(status_code=404, detail={"code": "LEASE_NOT_FOUND", "message": "Lease not found", "fieldErrors": {}})
    payments = await db.list_subdocs(land_service.payments_path(uid, lease_id))
    if any(p.get("month") == body.month for p in payments):
        raise HTTPException(status_code=409, detail={"code": "DUPLICATE_PAYMENT_MONTH", "message": "A payment for this month already exists", "fieldErrors": {}})
    payment_id = uuid4().hex
    doc = {"id": payment_id, "leaseId": lease_id, **body.model_dump()}
    await db.set_subdoc_at(land_service.payments_path(uid, lease_id), payment_id, doc)
    return doc


@router.get("/leases/{lease_id}/payments")
async def list_payments(lease_id: str, page: int = 1, pageSize: int = 20, uid: str = Depends(current_user_id)):
    await land_service.user_or_403(uid, *ROLES)
    lease = await db.get_subdoc_at(land_service.leases_path(uid), lease_id)
    if lease is None:
        raise HTTPException(status_code=404, detail={"code": "LEASE_NOT_FOUND", "message": "Lease not found", "fieldErrors": {}})
    payments = await db.list_subdocs(land_service.payments_path(uid, lease_id))
    payments.sort(key=lambda p: p.get("month", ""), reverse=True)
    total_collected = sum(p.get("amountRupees", 0) for p in payments)
    paid_months = {p.get("month") for p in payments}
    body = _envelope(payments, page, _page_size(pageSize))
    body["totalCollectedRupees"] = total_collected
    body["pendingMonths"] = land_service.pending_months(lease.get("startDate", ""), paid_months)
    return body
