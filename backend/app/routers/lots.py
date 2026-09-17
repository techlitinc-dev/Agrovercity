from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.core import db
from app.core.deps import require_roles
from app.models.lots import LotRequest

router = APIRouter(prefix="/market", tags=["lots"])


@router.post("/lots", status_code=201)
async def create_lot(body: LotRequest, user: dict = Depends(require_roles("farmer"))):
    if body.quantityQuintals <= 0:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "quantityQuintals must be greater than 0", "fieldErrors": {"quantityQuintals": "must be greater than 0"}},
        )
    if body.expectedRate < 0:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "expectedRate must be >= 0", "fieldErrors": {"expectedRate": "must be >= 0"}},
        )
    lot_id = f"lot_{uuid4().hex[:10]}"
    doc = {
        **body.model_dump(),
        "id": lot_id,
        "farmerId": user["id"],
        "status": "open",
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    await db.set_doc("market_lots", lot_id, doc)
    return doc


@router.get("/lots")
async def list_lots(
    status: str | None = None,
    page: int = 1,
    pageSize: int = 20,
    user: dict = Depends(require_roles("farmer")),
):
    docs = await db.query("market_lots", [("farmerId", "==", user["id"])], limit=1000)
    if status:
        docs = [d for d in docs if d.get("status") == status]
    total = len(docs)
    page_size = max(1, min(pageSize, 50))
    start = (max(1, page) - 1) * page_size
    return {"data": docs[start : start + page_size], "page": page, "pageSize": page_size, "total": total}


@router.put("/lots/{lot_id}")
async def update_lot(lot_id: str, body: LotRequest, user: dict = Depends(require_roles("farmer"))):
    lot = await db.get_doc("market_lots", lot_id)
    if lot is None or lot.get("farmerId") != user["id"]:
        raise HTTPException(
            status_code=404,
            detail={"code": "LOT_NOT_FOUND", "message": "Lot not found", "fieldErrors": {}},
        )
    if lot.get("status") == "sold":
        raise HTTPException(
            status_code=409,
            detail={"code": "LOT_NOT_EDITABLE", "message": "Sold lots cannot be edited", "fieldErrors": {}},
        )
    lot.update(body.model_dump())
    await db.set_doc("market_lots", lot_id, lot)
    return lot


@router.delete("/lots/{lot_id}")
async def withdraw_lot(lot_id: str, user: dict = Depends(require_roles("farmer"))):
    lot = await db.get_doc("market_lots", lot_id)
    if lot is None or lot.get("farmerId") != user["id"]:
        raise HTTPException(
            status_code=404,
            detail={"code": "LOT_NOT_FOUND", "message": "Lot not found", "fieldErrors": {}},
        )
    if lot.get("status") == "sold":
        raise HTTPException(
            status_code=409,
            detail={"code": "LOT_NOT_EDITABLE", "message": "Sold lots cannot be withdrawn", "fieldErrors": {}},
        )
    lot["status"] = "withdrawn"
    await db.set_doc("market_lots", lot_id, lot)
    return {"ok": True, "status": "withdrawn"}
