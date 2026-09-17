import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.core import db
from app.core.cache import cache_get, cache_set
from app.core.deps import require_roles

router = APIRouter(prefix="/mandi", tags=["mandi"])

MANDI_ROLES = ("farmer", "seller", "broker")
MAX_PAGE_SIZE = 50


def _crop_matches(doc: dict, crop: str) -> bool:
    return crop.lower() in doc.get("commodity", "").lower()


@router.get("/prices")
async def get_prices(
    crop: str | None = None,
    district: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
    page: int = 1,
    pageSize: int = 20,
    user: dict = Depends(require_roles(*MANDI_ROLES)),
):
    docs = await db.query("mandi_prices", [], limit=1000)
    if crop:
        docs = [d for d in docs if _crop_matches(d, crop)]
    if district:
        docs = [d for d in docs if d.get("district", "").lower() == district.lower()]
    total = len(docs)
    page_size = max(1, min(pageSize, MAX_PAGE_SIZE))
    start = (max(1, page) - 1) * page_size
    return {"data": docs[start : start + page_size], "page": page, "pageSize": page_size, "total": total}


@router.get("/list")
async def list_mandis(user: dict = Depends(require_roles(*MANDI_ROLES))):
    docs = await db.query("mandis", [], limit=1000)
    return {"data": docs}


@router.get("/vyapari-rates")
async def vyapari_rates(crops: str | None = None, user: dict = Depends(require_roles(*MANDI_ROLES))):
    key = f"vyapari_rates:{crops or 'all'}"
    cached = await cache_get(key)
    if cached is not None:
        return json.loads(cached)
    docs = await db.query("vyapari_rates", [], limit=1000)
    if crops:
        wanted = [c.strip().lower() for c in crops.split(",")]
        docs = [d for d in docs if any(w in d.get("crop", "").lower() for w in wanted)]
    payload = {"data": docs, "cachedAt": datetime.now(timezone.utc).isoformat()}
    await cache_set(key, json.dumps(payload), 7200)
    return payload


@router.get("/compare")
async def compare(
    crop: str,
    quantityQuintals: float,
    lat: float | None = None,
    lng: float | None = None,
    user: dict = Depends(require_roles(*MANDI_ROLES)),
):
    if quantityQuintals <= 0:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_QUANTITY", "message": "quantityQuintals must be greater than 0", "fieldErrors": {"quantityQuintals": "must be greater than 0"}},
        )
    docs = await db.query("mandi_prices", [], limit=1000)
    docs = [d for d in docs if _crop_matches(d, crop)]
    items = [
        {
            "mandiName": d["mandiName"],
            "modalPrice": d["modalPrice"],
            "transportCost": d["distanceKm"] * 12,
            "netProfit": d["modalPrice"] * quantityQuintals - d["distanceKm"] * 12,
        }
        for d in docs
    ]
    items.sort(key=lambda item: item["netProfit"], reverse=True)
    return {"data": items}


@router.get("/prices/history")
async def price_history(
    crop: str | None = None,
    mandi: str | None = None,
    months: int = 3,
    user: dict = Depends(require_roles(*MANDI_ROLES)),
):
    if not crop or not mandi:
        field_errors = {}
        if not crop:
            field_errors["crop"] = "required"
        if not mandi:
            field_errors["mandi"] = "required"
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "crop and mandi are required", "fieldErrors": field_errors},
        )
    months = max(1, min(months, 36))
    docs = await db.query("mandi_price_history", [], limit=10000)
    docs = [d for d in docs if _crop_matches(d, crop) and mandi.lower() in d.get("mandiName", "").lower()]
    docs.sort(key=lambda d: d["date"])
    docs = docs[-months * 30 :]
    return {"data": [{"date": d["date"], "modalPrice": d["modalPrice"]} for d in docs]}
