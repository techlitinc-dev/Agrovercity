def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _seed_order(fake_db, **overrides) -> dict:
    order = {
        "id": "order_1",
        "userId": "uid-1",
        "items": [{"productId": "prod-1", "quantity": 1}],
        "paymentMethod": "upi",
        "deliveryAddress": "Ozark",
        "total": 380,
        "status": "placed",
        "refundStatus": "none",
        "createdAt": "2026-09-17T00:00:00+00:00",
    }
    order.update(overrides)
    fake_db["orders"][order["id"]] = order
    return order


async def _login(client) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    return resp.json()["accessToken"]


async def test_cancel_placed_order(client, fake_firebase, fake_users, fake_db):
    _seed_order(fake_db)
    access = await _login(client)
    resp = await client.post("/v1/orders/order_1/cancel", headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cancelled"
    assert body["refundStatus"] == "none"


async def test_cancel_paid_order_requests_refund(client, fake_firebase, fake_users, fake_db):
    _seed_order(fake_db, status="paid", razorpayPaymentId="pay_dev_1")
    access = await _login(client)
    resp = await client.post("/v1/orders/order_1/cancel", headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json()["refundStatus"] == "requested"


async def test_cancel_shipped_order_409(client, fake_firebase, fake_users, fake_db):
    _seed_order(fake_db, status="shipped")
    access = await _login(client)
    resp = await client.post("/v1/orders/order_1/cancel", headers=_auth_header(access))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ORDER_NOT_CANCELLABLE"


async def test_cancel_other_users_order_404(client, fake_firebase, fake_users, fake_db):
    _seed_order(fake_db, userId="uid-2")
    access = await _login(client)
    resp = await client.post("/v1/orders/order_1/cancel", headers=_auth_header(access))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "ORDER_NOT_FOUND"


async def test_refund_dev_mode_processed(client, fake_firebase, fake_users, fake_db):
    _seed_order(fake_db, status="cancelled", razorpayPaymentId="pay_dev_1", refundStatus="requested")
    access = await _login(client)
    resp = await client.post("/v1/payments/razorpay/refund", json={"orderId": "order_1"}, headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "refundStatus": "processed"}
    assert fake_db["orders"]["order_1"]["razorpayRefundId"].startswith("rfnd_dev_")
    refund_id = fake_db["orders"]["order_1"]["razorpayRefundId"]

    resp = await client.post("/v1/payments/razorpay/refund", json={"orderId": "order_1"}, headers=_auth_header(access))
    assert resp.status_code == 200
    assert fake_db["orders"]["order_1"]["razorpayRefundId"] == refund_id


async def test_refund_not_applicable_409(client, fake_firebase, fake_users, fake_db):
    _seed_order(fake_db, status="placed")
    access = await _login(client)
    resp = await client.post("/v1/payments/razorpay/refund", json={"orderId": "order_1"}, headers=_auth_header(access))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "REFUND_NOT_APPLICABLE"
