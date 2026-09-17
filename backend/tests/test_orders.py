from scripts.seed_products import PRODUCTS

PRODUCT_PRICE = PRODUCTS[0]["discountedPrice"]


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    return resp.json()["accessToken"]


async def _seed_products(fake_db):
    for doc in PRODUCTS:
        fake_db["products"][doc["id"]] = doc


async def _add_to_cart(client, access, product_id="prod-1", quantity=2):
    resp = await client.post("/v1/cart/items", json={"productId": product_id, "quantity": quantity}, headers=_auth_header(access))
    assert resp.status_code == 200


def _place_body(**overrides) -> dict:
    return {
        "items": [{"productId": "prod-1", "quantity": 2}],
        "paymentMethod": "cod",
        "deliveryAddress": "Ozark, Dindori, Maharashtra - 422202",
        "idempotencyKey": "key-1",
        **overrides,
    }


async def test_place_order_and_clears_cart(client, fake_firebase, fake_users, fake_db):
    await _seed_products(fake_db)
    access = await _login(client, fake_users)
    await _add_to_cart(client, access)

    resp = await client.post("/v1/orders", json=_place_body(), headers=_auth_header(access))
    assert resp.status_code == 200
    order_id = resp.json()["orderId"]
    assert resp.json()["total"] == PRODUCT_PRICE * 2

    resp = await client.get("/v1/cart", headers=_auth_header(access))
    assert resp.json() == {"data": [], "cartTotal": 0}

    resp = await client.get(f"/v1/orders/{order_id}", headers=_auth_header(access))
    assert resp.json()["status"] == "placed"


async def test_order_idempotent(client, fake_firebase, fake_users, fake_db):
    await _seed_products(fake_db)
    access = await _login(client, fake_users)
    resp1 = await client.post("/v1/orders", json=_place_body(), headers=_auth_header(access))
    resp2 = await client.post("/v1/orders", json=_place_body(), headers=_auth_header(access))
    assert resp1.json()["orderId"] == resp2.json()["orderId"]

    resp = await client.get("/v1/orders", headers=_auth_header(access))
    assert resp.json()["total"] == 1


async def test_bnpl_schedule(client, fake_firebase, fake_users, fake_db):
    await _seed_products(fake_db)
    access = await _login(client, fake_users)
    resp = await client.post("/v1/orders", json=_place_body(paymentMethod="bnpl"), headers=_auth_header(access))
    assert resp.status_code == 200
    schedule = resp.json()["bnplSchedule"]
    assert len(schedule) == 2
    assert sum(i["amount"] for i in schedule) == resp.json()["total"]


async def test_orders_list_and_detail(client, fake_firebase, fake_users, fake_db):
    from app.services.tokens import create_access_token

    await _seed_products(fake_db)
    fake_users["users"]["uid-2"] = {"id": "uid-2", "activeProfile": "farmer", "linkedProfiles": ["farmer"]}
    access = await _login(client, fake_users)
    resp = await client.post("/v1/orders", json=_place_body(), headers=_auth_header(access))
    order_id = resp.json()["orderId"]

    resp = await client.get("/v1/orders", headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    resp = await client.get(f"/v1/orders/{order_id}", headers=_auth_header(access))
    assert resp.status_code == 200

    resp = await client.get(f"/v1/orders/{order_id}", headers=_auth_header(create_access_token("uid-2")))
    assert resp.status_code == 403


async def test_razorpay_order_and_verify_dev_mode(client, fake_firebase, fake_users, fake_db):
    await _seed_products(fake_db)
    access = await _login(client, fake_users)
    resp = await client.post("/v1/orders", json=_place_body(paymentMethod="upi"), headers=_auth_header(access))
    order_id = resp.json()["orderId"]

    resp = await client.post("/v1/payments/razorpay/order", json={"orderId": order_id}, headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["razorpayOrderId"].startswith("order_dev_")
    assert body["keyId"] == "rzp_test_dev"

    resp = await client.post(
        "/v1/payments/razorpay/verify",
        json={
            "orderId": order_id,
            "razorpayOrderId": body["razorpayOrderId"],
            "razorpayPaymentId": "pay_dev_1",
            "razorpaySignature": "dev",
        },
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "paid"


async def test_razorpay_verify_bad_signature(client, fake_firebase, fake_users, fake_db):
    await _seed_products(fake_db)
    access = await _login(client, fake_users)
    resp = await client.post("/v1/orders", json=_place_body(paymentMethod="upi"), headers=_auth_header(access))
    order_id = resp.json()["orderId"]

    resp = await client.post("/v1/payments/razorpay/order", json={"orderId": order_id}, headers=_auth_header(access))
    razorpay_order_id = resp.json()["razorpayOrderId"]

    resp = await client.post(
        "/v1/payments/razorpay/verify",
        json={
            "orderId": order_id,
            "razorpayOrderId": razorpay_order_id,
            "razorpayPaymentId": "pay_dev_1",
            "razorpaySignature": "wrong",
        },
        headers=_auth_header(access),
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "PAYMENT_SIGNATURE_INVALID"
