from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.core import db
from app.core.deps import require_roles
from app.models.tree import SaplingRequestIn

router = APIRouter(prefix="/tree", tags=["tree"])

ROLES = ("farmer", "farmLandlord", "seller")


def _envelope(data: list[dict], page: int, page_size: int) -> dict:
    total = len(data)
    start = (max(1, page) - 1) * page_size
    return {"data": data[start : start + page_size], "page": page, "pageSize": page_size, "total": total}


def _page_size(pageSize: int) -> int:
    return max(1, min(pageSize, 50))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/articles")
async def list_articles(category: str | None = None, page: int = 1, pageSize: int = 20, user: dict = Depends(require_roles(*ROLES))):
    docs = await db.query("tree_articles", [], limit=1000)
    if category:
        docs = [d for d in docs if d.get("category") == category]
    return _envelope(docs, page, _page_size(pageSize))


@router.get("/ngos")
async def list_ngos(page: int = 1, pageSize: int = 20, user: dict = Depends(require_roles(*ROLES))):
    docs = await db.query("ngos", [], limit=1000)
    return _envelope(docs, page, _page_size(pageSize))


@router.post("/ngos/{ngo_id}/sapling-request", status_code=201)
async def request_saplings(ngo_id: str, body: SaplingRequestIn, user: dict = Depends(require_roles(*ROLES))):
    ngo = await db.get_doc("ngos", ngo_id)
    if ngo is None:
        raise HTTPException(status_code=404, detail={"code": "NGO_NOT_FOUND", "message": "NGO not found", "fieldErrors": {}})
    request_id = f"sap_{uuid4().hex[:10]}"
    await db.set_subdoc_at(
        f"users/{user['id']}/sapling_requests",
        request_id,
        {
            "id": request_id,
            "ngoId": ngo_id,
            "ngoName": ngo.get("name"),
            "treeType": body.treeType,
            "count": body.count,
            "status": "requested",
            "createdAt": _now_iso(),
        },
    )
    return {"requestId": request_id, "status": "requested"}


@router.get("/biofuel")
async def list_biofuel(page: int = 1, pageSize: int = 20, user: dict = Depends(require_roles(*ROLES))):
    docs = await db.query("biofuel_trees", [], limit=1000)
    return _envelope(docs, page, _page_size(pageSize))


@router.get("/care-guides")
async def list_care_guides(page: int = 1, pageSize: int = 20, user: dict = Depends(require_roles(*ROLES))):
    docs = await db.query("tree_care_guides", [], limit=1000)
    docs.sort(key=lambda d: d.get("stepNumber", 0))
    return _envelope(docs, page, _page_size(pageSize))
