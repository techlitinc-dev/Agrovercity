from scripts.seed_products import CERTIFICATES, PRODUCTS

PRODUCT_1 = PRODUCTS[0]


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    return resp.json()["accessToken"]


async def test_products_list_and_category_filter(client, fake_firebase, fake_users, fake_db):
    for doc in PRODUCTS:
        fake_db["products"][doc["id"]] = doc
    access = await _login(client)
    resp = await client.get("/v1/products", params={"category": "seeds"}, headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["data"][0]["category"] == "seeds"


async def test_products_query_search(client, fake_firebase, fake_users, fake_db):
    for doc in PRODUCTS:
        fake_db["products"][doc["id"]] = doc
    access = await _login(client)
    resp = await client.get("/v1/products", params={"query": "urea"}, headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert "Urea" in body["data"][0]["title"]


async def test_product_404(client, fake_firebase, fake_users, fake_db):
    for doc in PRODUCTS:
        fake_db["products"][doc["id"]] = doc
    access = await _login(client)
    resp = await client.get("/v1/products/nope", headers=_auth_header(access))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PRODUCT_NOT_FOUND"


async def test_certificate_by_batch(client, fake_firebase, fake_users, fake_db):
    for doc in PRODUCTS:
        fake_db["products"][doc["id"]] = doc
    for doc in CERTIFICATES:
        fake_db["certificates"][doc["batchNo"]] = doc
    access = await _login(client)
    resp = await client.get(f"/v1/products/{PRODUCT_1['id']}/certificate", headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert "AGMARK" in body["certifier"]
    assert body["batchNo"] == PRODUCT_1["batchNo"]


async def test_cart_add_update_delete(client, fake_firebase, fake_users, fake_db):
    for doc in PRODUCTS:
        fake_db["products"][doc["id"]] = doc
    access = await _login(client)

    resp = await client.post("/v1/cart/items", json={"productId": "prod-1", "quantity": 2}, headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json()["cartTotal"] == PRODUCT_1["discountedPrice"] * 2

    resp = await client.put("/v1/cart/items/prod-1", json={"quantity": 1}, headers=_auth_header(access))
    assert resp.json()["cartTotal"] == PRODUCT_1["discountedPrice"]

    resp = await client.delete("/v1/cart/items/prod-1", headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json() == {"data": [], "cartTotal": 0}


async def test_cart_add_unknown_product_404(client, fake_firebase, fake_users, fake_db):
    access = await _login(client)
    resp = await client.post("/v1/cart/items", json={"productId": "nope", "quantity": 1}, headers=_auth_header(access))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PRODUCT_NOT_FOUND"
