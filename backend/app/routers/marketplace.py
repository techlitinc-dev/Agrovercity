from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.core import db
from app.core.deps import require_roles
from app.models.marketplace import CartItemRequest, CartItemUpdateRequest
from app.models.reviews import ReviewIn, ReviewOut

router = APIRouter(tags=["marketplace"])

MARKETPLACE_ROLES = ("farmer", "farmLandlord", "transport", "seller")
CATEGORIES = {"seeds", "vehicles", "fertilizer", "pesticide", "tools"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _cart_payload(uid: str) -> dict:
    cart = await db.get_doc("carts", uid) or {"userId": uid, "items": {}}
    data = []
    total = 0.0
    for pid, qty in cart.get("items", {}).items():
        product = await db.get_doc("products", pid)
        if product is None:
            continue
        data.append({"productId": pid, "quantity": qty, "product": product})
        total += product.get("discountedPrice", 0) * qty
    return {"data": data, "cartTotal": total}


async def _save_cart(uid: str, items: dict):
    await db.set_doc("carts", uid, {"userId": uid, "items": items, "updatedAt": _now_iso()})


@router.get("/products")
async def list_products(
    category: str | None = None,
    query: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
    page: int = 1,
    pageSize: int = 20,
    user: dict = Depends(require_roles(*MARKETPLACE_ROLES)),
):
    docs = await db.query("products", [], limit=1000)
    if category:
        docs = [d for d in docs if d.get("category") == category]
    if query:
        q = query.lower()
        docs = [d for d in docs if q in d.get("title", "").lower() or q in d.get("vernacularTitle", "").lower()]
    total = len(docs)
    page_size = max(1, min(pageSize, 50))
    start = (max(1, page) - 1) * page_size
    return {"data": docs[start : start + page_size], "page": page, "pageSize": page_size, "total": total}


@router.get("/products/{product_id}")
async def get_product(product_id: str, user: dict = Depends(require_roles(*MARKETPLACE_ROLES))):
    product = await db.get_doc("products", product_id)
    if product is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "PRODUCT_NOT_FOUND", "message": "Product not found", "fieldErrors": {}},
        )
    return product


@router.get("/products/{product_id}/certificate")
async def get_certificate(product_id: str, user: dict = Depends(require_roles(*MARKETPLACE_ROLES))):
    product = await db.get_doc("products", product_id)
    if product is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "PRODUCT_NOT_FOUND", "message": "Product not found", "fieldErrors": {}},
        )
    certificate = await db.get_doc("certificates", product.get("batchNo", ""))
    if certificate is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "CERTIFICATE_NOT_FOUND", "message": "Certificate not found for this batch", "fieldErrors": {}},
        )
    return certificate


@router.get("/cart")
async def get_cart(user: dict = Depends(require_roles(*MARKETPLACE_ROLES))):
    return await _cart_payload(user["id"])


@router.post("/cart/items")
async def add_cart_item(body: CartItemRequest, user: dict = Depends(require_roles(*MARKETPLACE_ROLES))):
    product = await db.get_doc("products", body.productId)
    if product is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "PRODUCT_NOT_FOUND", "message": "Product not found", "fieldErrors": {}},
        )
    if body.quantity < 1:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "quantity must be >= 1", "fieldErrors": {"quantity": "must be >= 1"}},
        )
    cart = await db.get_doc("carts", user["id"]) or {"userId": user["id"], "items": {}}
    items = dict(cart.get("items", {}))
    items[body.productId] = items.get(body.productId, 0) + body.quantity
    await _save_cart(user["id"], items)
    return await _cart_payload(user["id"])


@router.put("/cart/items/{product_id}")
async def update_cart_item(product_id: str, body: CartItemUpdateRequest, user: dict = Depends(require_roles(*MARKETPLACE_ROLES))):
    cart = await db.get_doc("carts", user["id"]) or {"userId": user["id"], "items": {}}
    items = dict(cart.get("items", {}))
    if product_id in items:
        if body.quantity <= 0:
            items.pop(product_id)
        else:
            items[product_id] = body.quantity
        await _save_cart(user["id"], items)
    return await _cart_payload(user["id"])


@router.delete("/cart/items/{product_id}")
async def remove_cart_item(product_id: str, user: dict = Depends(require_roles(*MARKETPLACE_ROLES))):
    cart = await db.get_doc("carts", user["id"]) or {"userId": user["id"], "items": {}}
    items = dict(cart.get("items", {}))
    items.pop(product_id, None)
    await _save_cart(user["id"], items)
    return await _cart_payload(user["id"])


@router.get("/products/{product_id}/reviews")
async def list_reviews(product_id: str, page: int = 1, pageSize: int = 20, user: dict = Depends(require_roles(*MARKETPLACE_ROLES))):
    product = await db.get_doc("products", product_id)
    if product is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "PRODUCT_NOT_FOUND", "message": "Product not found", "fieldErrors": {}},
        )
    reviews = await db.list_subdocs(f"products/{product_id}/reviews")
    reviews.sort(key=lambda r: r.get("updatedAt", ""), reverse=True)
    total = len(reviews)
    page_size = max(1, min(pageSize, 50))
    start = (max(1, page) - 1) * page_size
    return {"data": reviews[start : start + page_size], "page": page, "pageSize": page_size, "total": total}


@router.post("/products/{product_id}/reviews")
async def post_review(product_id: str, body: ReviewIn, user: dict = Depends(require_roles(*MARKETPLACE_ROLES))):
    product = await db.get_doc("products", product_id)
    if product is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "PRODUCT_NOT_FOUND", "message": "Product not found", "fieldErrors": {}},
        )
    uid = user["id"]
    reviews_path = f"products/{product_id}/reviews"
    existing = await db.get_subdoc_at(reviews_path, uid)
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": uid,
        "userId": uid,
        "userName": user.get("name") or "Farmer",
        "rating": body.rating,
        "comment": body.comment,
        "createdAt": (existing or {}).get("createdAt", now),
        "updatedAt": now,
    }
    await db.set_subdoc_at(reviews_path, uid, doc)

    reviews = await db.list_subdocs(reviews_path)
    product["ratingCount"] = len(reviews)
    product["ratingAvg"] = round(sum(r.get("rating", 0) for r in reviews) / len(reviews), 1) if reviews else None
    await db.set_doc("products", product_id, product)
    return ReviewOut(**doc)
