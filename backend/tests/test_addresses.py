def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


ADDRESS_BODY = {
    "label": "घर",
    "line1": "House 12, Main Road",
    "village": "Ozark",
    "district": "Nashik",
    "state": "Maharashtra",
    "pincode": "422202",
}


async def _login(client) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    return resp.json()["accessToken"]


async def test_create_first_address_becomes_default(client, fake_firebase, fake_users, fake_db):
    access = await _login(client)
    resp = await client.post("/v1/addresses", json=ADDRESS_BODY, headers=_auth_header(access))
    assert resp.status_code == 201
    assert resp.json()["isDefault"] is True


async def test_second_default_clears_first(client, fake_firebase, fake_users, fake_db):
    access = await _login(client)
    await client.post("/v1/addresses", json=ADDRESS_BODY, headers=_auth_header(access))
    resp = await client.post("/v1/addresses", json={**ADDRESS_BODY, "label": "खेत", "isDefault": True}, headers=_auth_header(access))
    second_id = resp.json()["id"]

    resp = await client.get("/v1/addresses", headers=_auth_header(access))
    data = resp.json()["data"]
    assert data[0]["id"] == second_id
    assert data[0]["isDefault"] is True
    assert sum(1 for d in data if d["isDefault"]) == 1


async def test_update_pincode(client, fake_firebase, fake_users, fake_db):
    access = await _login(client)
    resp = await client.post("/v1/addresses", json=ADDRESS_BODY, headers=_auth_header(access))
    address_id = resp.json()["id"]
    resp = await client.put(
        f"/v1/addresses/{address_id}",
        json={**ADDRESS_BODY, "pincode": "422003"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    assert resp.json()["pincode"] == "422003"


async def test_delete_default_promotes_next(client, fake_firebase, fake_users, fake_db):
    access = await _login(client)
    resp = await client.post("/v1/addresses", json=ADDRESS_BODY, headers=_auth_header(access))
    first_id = resp.json()["id"]
    resp = await client.post("/v1/addresses", json={**ADDRESS_BODY, "label": "खेत", "isDefault": True}, headers=_auth_header(access))
    second_id = resp.json()["id"]

    resp = await client.delete(f"/v1/addresses/{second_id}", headers=_auth_header(access))
    assert resp.status_code == 204

    resp = await client.get("/v1/addresses", headers=_auth_header(access))
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["id"] == first_id
    assert data[0]["isDefault"] is True


async def test_other_users_address_404(client, fake_firebase, fake_users, fake_db):
    from app.services.tokens import create_access_token

    fake_users["users"]["uid-2"] = {"id": "uid-2", "activeProfile": "farmer", "linkedProfiles": ["farmer"]}
    access = await _login(client)
    resp = await client.post("/v1/addresses", json=ADDRESS_BODY, headers=_auth_header(access))
    address_id = resp.json()["id"]

    resp = await client.put(
        f"/v1/addresses/{address_id}",
        json=ADDRESS_BODY,
        headers=_auth_header(create_access_token("uid-2")),
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "ADDRESS_NOT_FOUND"


async def test_bad_pincode_422(client, fake_firebase, fake_users, fake_db):
    access = await _login(client)
    resp = await client.post("/v1/addresses", json={**ADDRESS_BODY, "pincode": "42"}, headers=_auth_header(access))
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_place_order_with_address_id(client, fake_firebase, fake_users, fake_db):
    from scripts.seed_products import PRODUCTS

    for doc in PRODUCTS:
        fake_db["products"][doc["id"]] = doc
    access = await _login(client)
    resp = await client.post("/v1/addresses", json=ADDRESS_BODY, headers=_auth_header(access))
    address_id = resp.json()["id"]

    resp = await client.post(
        "/v1/orders",
        json={
            "items": [{"productId": "prod-1", "quantity": 1}],
            "paymentMethod": "cod",
            "deliveryAddress": "fallback",
            "idempotencyKey": "key-addr-1",
            "addressId": address_id,
        },
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    order_id = resp.json()["orderId"]

    resp = await client.get(f"/v1/orders/{order_id}", headers=_auth_header(access))
    delivery = resp.json()["deliveryAddress"]
    assert "Ozark" in delivery
    assert "422202" in delivery
