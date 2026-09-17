from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.core import db
from app.core.config import settings
from app.core.deps import require_roles
from app.models.marketplace import PlaceOrderRequest, RazorpayOrderRequest, RazorpayRefundRequest, RazorpayVerifyRequest
from app.services import payments

router = APIRouter(tags=["orders"])

MARKETPLACE_ROLES = ("farmer", "farmLandlord", "transport", "seller")
PAYMENT_METHODS = {"upi", "cod", "bnpl"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("/orders")
async def place_order(body: PlaceOrderRequest, user: dict = Depends(require_roles(*MARKETPLACE_ROLES))):
    seen = await db.get_doc("idempotency_keys", body.idempotencyKey)
    if seen is not None:
        return seen["response"]

    if body.paymentMethod not in PAYMENT_METHODS:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "Invalid payment method", "fieldErrors": {"paymentMethod": "must be upi, cod or bnpl"}},
        )
    if not body.items:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "items must not be empty", "fieldErrors": {"items": "at least one item required"}},
        )
    for item in body.items:
        if item.quantity < 1:
            raise HTTPException(
                status_code=422,
                detail={"code": "VALIDATION_ERROR", "message": "quantity must be >= 1", "fieldErrors": {"quantity": "must be >= 1"}},
            )

    delivery_address = body.deliveryAddress
    if body.addressId:
        address = await db.get_doc("addresses", body.addressId)
        if address is None or address.get("userId") != user["id"]:
            raise HTTPException(
                status_code=404,
                detail={"code": "ADDRESS_NOT_FOUND", "message": "Address not found", "fieldErrors": {}},
            )
        delivery_address = f"{address['line1']}, {address['village']}, {address['district']}, {address['state']} - {address['pincode']}"

    items_out = []
    total = 0
    for item in body.items:
        product = await db.get_doc("products", item.productId)
        if product is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "PRODUCT_NOT_FOUND", "message": f"Product {item.productId} not found", "fieldErrors": {}},
            )
        items_out.append({"productId": item.productId, "quantity": item.quantity})
        total += int(product.get("discountedPrice", 0)) * item.quantity

    order_id = f"order_{uuid4().hex[:10]}"
    order = {
        "id": order_id,
        "userId": user["id"],
        "items": items_out,
        "paymentMethod": body.paymentMethod,
        "deliveryAddress": delivery_address,
        "total": total,
        "status": "placed",
        "refundStatus": "none",
        "createdAt": _now_iso(),
    }
    await db.set_doc("orders", order_id, order)
    await db.set_doc("carts", user["id"], {"userId": user["id"], "items": {}, "updatedAt": _now_iso()})

    response = {"orderId": order_id, "total": total}
    if body.paymentMethod == "bnpl":
        first = total // 2
        response["bnplSchedule"] = [
            {"installment": 1, "dueInDays": 30, "amount": first},
            {"installment": 2, "dueInDays": 60, "amount": total - first},
        ]
    await db.set_doc("idempotency_keys", body.idempotencyKey, {"orderId": order_id, "response": response, "createdAt": _now_iso()})
    return response


@router.get("/orders")
async def list_orders(page: int = 1, pageSize: int = 20, user: dict = Depends(require_roles(*MARKETPLACE_ROLES))):
    docs = await db.query("orders", [("userId", "==", user["id"])], limit=1000)
    docs.sort(key=lambda d: d.get("createdAt", ""), reverse=True)
    total = len(docs)
    page_size = max(1, min(pageSize, 50))
    start = (max(1, page) - 1) * page_size
    return {"data": docs[start : start + page_size], "page": page, "pageSize": page_size, "total": total}


@router.get("/orders/{order_id}")
async def get_order(order_id: str, user: dict = Depends(require_roles(*MARKETPLACE_ROLES))):
    order = await db.get_doc("orders", order_id)
    if order is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "ORDER_NOT_FOUND", "message": "Order not found", "fieldErrors": {}},
        )
    if order.get("userId") != user["id"]:
        raise HTTPException(
            status_code=403,
            detail={"code": "ORDER_ACCESS_DENIED", "message": "Order does not belong to this user", "fieldErrors": {}},
        )
    return order


@router.post("/payments/razorpay/order")
async def create_razorpay_order(body: RazorpayOrderRequest, user: dict = Depends(require_roles(*MARKETPLACE_ROLES))):
    order = await db.get_doc("orders", body.orderId)
    if order is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "ORDER_NOT_FOUND", "message": "Order not found", "fieldErrors": {}},
        )
    if order.get("userId") != user["id"]:
        raise HTTPException(
            status_code=403,
            detail={"code": "ORDER_ACCESS_DENIED", "message": "Order does not belong to this user", "fieldErrors": {}},
        )
    rp_order = payments.create_razorpay_order(int(order["total"] * 100), order["id"])
    order["razorpayOrderId"] = rp_order["id"]
    await db.set_doc("orders", order["id"], order)
    return {
        "razorpayOrderId": rp_order["id"],
        "amount": rp_order["amount"],
        "currency": "INR",
        "keyId": settings.razorpay_key_id or "rzp_test_dev",
    }


@router.post("/payments/razorpay/verify")
async def verify_razorpay_payment(body: RazorpayVerifyRequest, user: dict = Depends(require_roles(*MARKETPLACE_ROLES))):
    order = await db.get_doc("orders", body.orderId)
    if order is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "ORDER_NOT_FOUND", "message": "Order not found", "fieldErrors": {}},
        )
    if order.get("userId") != user["id"]:
        raise HTTPException(
            status_code=403,
            detail={"code": "ORDER_ACCESS_DENIED", "message": "Order does not belong to this user", "fieldErrors": {}},
        )
    if not payments.verify_razorpay_signature(body.razorpayOrderId, body.razorpayPaymentId, body.razorpaySignature):
        raise HTTPException(
            status_code=400,
            detail={"code": "PAYMENT_SIGNATURE_INVALID", "message": "Razorpay signature verification failed", "fieldErrors": {}},
        )
    order["status"] = "paid"
    order["razorpayPaymentId"] = body.razorpayPaymentId
    await db.set_doc("orders", order["id"], order)
    return {"ok": True, "status": "paid"}


@router.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: str, user: dict = Depends(require_roles(*MARKETPLACE_ROLES))):
    order = await db.get_doc("orders", order_id)
    if order is None or order.get("userId") != user["id"]:
        raise HTTPException(
            status_code=404,
            detail={"code": "ORDER_NOT_FOUND", "message": "Order not found", "fieldErrors": {}},
        )
    if order.get("status") not in {"placed", "paid"}:
        raise HTTPException(
            status_code=409,
            detail={"code": "ORDER_NOT_CANCELLABLE", "message": "Order can no longer be cancelled", "fieldErrors": {}},
        )
    order["status"] = "cancelled"
    order["cancelledAt"] = _now_iso()
    if order.get("razorpayPaymentId"):
        order["refundStatus"] = "requested"
    await db.set_doc("orders", order_id, order)
    return order


@router.post("/payments/razorpay/refund")
async def refund_payment(body: RazorpayRefundRequest, user: dict = Depends(require_roles(*MARKETPLACE_ROLES))):
    order = await db.get_doc("orders", body.orderId)
    if order is None or order.get("userId") != user["id"]:
        raise HTTPException(
            status_code=404,
            detail={"code": "ORDER_NOT_FOUND", "message": "Order not found", "fieldErrors": {}},
        )
    if order.get("refundStatus") == "processed":
        return {"ok": True, "refundStatus": "processed"}
    if order.get("status") != "cancelled" or order.get("refundStatus") != "requested" or not order.get("razorpayPaymentId"):
        raise HTTPException(
            status_code=409,
            detail={"code": "REFUND_NOT_APPLICABLE", "message": "Refund is not applicable for this order", "fieldErrors": {}},
        )
    refund = await payments.refund_razorpay_payment(order["razorpayPaymentId"], int(order["total"] * 100))
    order["refundStatus"] = "processed"
    order["razorpayRefundId"] = refund["id"]
    await db.set_doc("orders", order["id"], order)
    return {"ok": True, "refundStatus": "processed"}
