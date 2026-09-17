from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.core import db
from app.core.deps import require_roles
from app.models.livestock import DairyOrderIn, ManureOrderIn, VetBookIn

router = APIRouter(tags=["livestock"])


def _envelope(data: list[dict], page: int, page_size: int) -> dict:
    total = len(data)
    start = (max(1, page) - 1) * page_size
    return {"data": data[start : start + page_size], "page": page, "pageSize": page_size, "total": total}


def _page_size(pageSize: int) -> int:
    return max(1, min(pageSize, 50))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/gaushalas")
async def list_gaushalas(district: str | None = None, lat: float | None = None, lng: float | None = None, page: int = 1, pageSize: int = 20, user: dict = Depends(require_roles("farmer", "seller"))):
    docs = await db.query("gaushalas", [], limit=1000)
    if district:
        docs = [d for d in docs if d.get("district", "").lower() == district.lower()]
    return _envelope(docs, page, _page_size(pageSize))


@router.post("/gaushalas/{gaushala_id}/manure-order", status_code=201)
async def manure_order(gaushala_id: str, body: ManureOrderIn, user: dict = Depends(require_roles("farmer"))):
    gaushala = await db.get_doc("gaushalas", gaushala_id)
    if gaushala is None:
        raise HTTPException(status_code=404, detail={"code": "GAUSHALA_NOT_FOUND", "message": "Gaushala not found", "fieldErrors": {}})
    order_id = f"mord_{uuid4().hex[:10]}"
    await db.set_subdoc_at(
        f"users/{user['id']}/manure_orders",
        order_id,
        {"id": order_id, "product": body.product, "quantity": body.quantity, "gaushalaId": gaushala_id, "status": "placed", "createdAt": _now_iso()},
    )
    return {"orderId": order_id, "status": "placed"}


@router.get("/nurseries")
async def list_nurseries(lat: float | None = None, lng: float | None = None, page: int = 1, pageSize: int = 20, user: dict = Depends(require_roles("farmer", "seller"))):
    docs = await db.query("nurseries", [], limit=1000)
    docs.sort(key=lambda d: d.get("distanceKm", 0))
    return _envelope(docs, page, _page_size(pageSize))


@router.get("/vets")
async def list_vets(lat: float | None = None, lng: float | None = None, emergency: bool = False, page: int = 1, pageSize: int = 20, user: dict = Depends(require_roles("farmer"))):
    docs = await db.query("vets", [], limit=1000)
    if emergency:
        docs = [d for d in docs if d.get("emergencyAvailable")]
    docs.sort(key=lambda d: d.get("distanceKm", 0))
    docs = [{**d, **await _provider_rating(d["id"])} for d in docs]
    return _envelope(docs, page, _page_size(pageSize))


async def _provider_rating(provider_id: str) -> dict:
    agg = await db.get_doc("provider_ratings", provider_id)
    if agg is None:
        return {"ratingAvg": None, "ratingCount": 0}
    return {"ratingAvg": agg.get("ratingAvg"), "ratingCount": agg.get("ratingCount", 0)}


@router.post("/vets/{vet_id}/book", status_code=201)
async def book_vet(vet_id: str, body: VetBookIn, user: dict = Depends(require_roles("farmer"))):
    vet = await db.get_doc("vets", vet_id)
    if vet is None:
        raise HTTPException(status_code=404, detail={"code": "VET_NOT_FOUND", "message": "Vet not found", "fieldErrors": {}})
    if body.visitType == "farm" and not vet.get("availableForFarmVisit"):
        raise HTTPException(status_code=400, detail={"code": "FARM_VISIT_UNAVAILABLE", "message": "यह डॉक्टर फ़ार्म विज़िट नहीं करते", "fieldErrors": {}})
    booking_id = f"vetbk_{uuid4().hex[:10]}"
    doc = {
        "id": booking_id,
        "vetId": vet_id,
        "vetName": vet.get("name", ""),
        "visitType": body.visitType,
        "slot": body.slot,
        "animalType": body.animalType,
        "consultationFeeRupees": vet.get("consultationFeeRupees", 0),
        "status": "confirmed",
        "createdAt": _now_iso(),
    }
    await db.set_subdoc_at(f"users/{user['id']}/vet_bookings", booking_id, doc)
    return doc


@router.post("/vets/bookings/{booking_id}/complete")
async def complete_vet_booking(booking_id: str, user: dict = Depends(require_roles("farmer"))):
    booking = await db.get_subdoc_at(f"users/{user['id']}/vet_bookings", booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail={"code": "BOOKING_NOT_FOUND", "message": "Booking not found", "fieldErrors": {}})
    booking["status"] = "completed"
    await db.set_subdoc_at(f"users/{user['id']}/vet_bookings", booking_id, booking)
    return booking


@router.get("/dairy-products")
async def list_dairy(category: str | None = None, page: int = 1, pageSize: int = 20, user: dict = Depends(require_roles("farmer", "seller"))):
    docs = await db.query("dairy_products", [], limit=1000)
    if category:
        docs = [d for d in docs if d.get("category") == category]
    return _envelope(docs, page, _page_size(pageSize))


@router.post("/dairy-products/{product_id}/order", status_code=201)
async def order_dairy(product_id: str, body: DairyOrderIn, user: dict = Depends(require_roles("farmer", "seller"))):
    product = await db.get_doc("dairy_products", product_id)
    if product is None:
        raise HTTPException(status_code=404, detail={"code": "PRODUCT_NOT_FOUND", "message": "Product not found", "fieldErrors": {}})
    if not product.get("inStock"):
        raise HTTPException(status_code=409, detail={"code": "OUT_OF_STOCK", "message": "स्टॉक में नहीं", "fieldErrors": {}})
    order_id = f"dord_{uuid4().hex[:10]}"
    total = round(product.get("priceRupees", 0) * body.quantity, 2)
    await db.set_subdoc_at(
        f"users/{user['id']}/dairy_orders",
        order_id,
        {
            "id": order_id,
            "productId": product_id,
            "productName": product.get("name"),
            "quantity": body.quantity,
            "total": total,
            "status": "placed",
            "createdAt": _now_iso(),
        },
    )
    return {"orderId": order_id, "total": total}
