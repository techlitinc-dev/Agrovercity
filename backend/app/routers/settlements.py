from fastapi import APIRouter, Depends

from app.core import db
from app.core.deps import require_roles

router = APIRouter(tags=["settlements"])


async def _my_settlements(role: str, uid: str, page: int, page_size: int) -> dict:
    docs = await db.query("settlements", [("entityId", "==", uid)], limit=1000)
    docs = [d for d in docs if d.get("role") == role]
    docs.sort(key=lambda d: d.get("periodStart", ""), reverse=True)
    total = len(docs)
    start = (max(1, page) - 1) * page_size
    return {"data": docs[start : start + page_size], "page": page, "pageSize": page_size, "total": total}


@router.get("/transport/settlements")
async def transport_settlements(page: int = 1, pageSize: int = 20, user: dict = Depends(require_roles("transport"))):
    return await _my_settlements("transport", user["id"], page, max(1, min(pageSize, 50)))


@router.get("/equipment/settlements")
async def equipment_settlements(page: int = 1, pageSize: int = 20, user: dict = Depends(require_roles("equipmentRental"))):
    return await _my_settlements("equipmentRental", user["id"], page, max(1, min(pageSize, 50)))


@router.get("/broker/settlements")
async def broker_settlements(page: int = 1, pageSize: int = 20, user: dict = Depends(require_roles("broker"))):
    return await _my_settlements("broker", user["id"], page, max(1, min(pageSize, 50)))
