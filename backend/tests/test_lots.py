def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


LOT_BODY = {
    "crop": "Tomato",
    "quantityQuintals": 12.5,
    "expectedRate": 2100,
    "harvestDate": "2026-09-10",
    "photos": [],
    "location": {"lat": 20.0, "lng": 73.8},
}


async def _login(client, fake_users, profile="farmer") -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    access = resp.json()["accessToken"]
    fake_users["users"]["uid-1"]["activeProfile"] = profile
    fake_users["users"]["uid-1"]["id"] = "uid-1"
    return access


async def _create_lot(client, access, **overrides) -> dict:
    resp = await client.post("/v1/market/lots", json={**LOT_BODY, **overrides}, headers=_auth_header(access))
    assert resp.status_code == 201
    return resp.json()


async def test_create_lot(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    body = await _create_lot(client, access)
    assert body["status"] == "open"
    assert body["farmerId"] == "uid-1"
    assert body["id"].startswith("lot_")


async def test_list_own_lots_only(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    await _create_lot(client, access)
    fake_db["market_lots"]["other"] = {
        "id": "lot_other",
        "farmerId": "uid-2",
        "crop": "Onion",
        "quantityQuintals": 3,
        "expectedRate": 1800,
        "harvestDate": "2026-09-01",
        "photos": [],
        "location": {"lat": 20.0, "lng": 73.8},
        "status": "open",
        "createdAt": "2026-09-01T00:00:00+00:00",
    }
    resp = await client.get("/v1/market/lots", headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["data"][0]["farmerId"] == "uid-1"


async def test_update_lot(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    lot = await _create_lot(client, access)
    resp = await client.put(
        f"/v1/market/lots/{lot['id']}",
        json={**LOT_BODY, "quantityQuintals": 20},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    assert resp.json()["quantityQuintals"] == 20


async def test_withdraw_lot(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    lot = await _create_lot(client, access)
    resp = await client.delete(f"/v1/market/lots/{lot['id']}", headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "status": "withdrawn"}

    resp = await client.get("/v1/market/lots", params={"status": "open"}, headers=_auth_header(access))
    assert resp.json()["total"] == 0

    resp = await client.get("/v1/market/lots", params={"status": "withdrawn"}, headers=_auth_header(access))
    assert resp.json()["total"] == 1


async def test_update_other_farmers_lot_404(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    fake_db["market_lots"]["other"] = {
        "id": "lot_other",
        "farmerId": "uid-2",
        "crop": "Onion",
        "quantityQuintals": 3,
        "expectedRate": 1800,
        "harvestDate": "2026-09-01",
        "photos": [],
        "location": {"lat": 20.0, "lng": 73.8},
        "status": "open",
        "createdAt": "2026-09-01T00:00:00+00:00",
    }
    resp = await client.put(
        "/v1/market/lots/lot_other",
        json=LOT_BODY,
        headers=_auth_header(access),
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "LOT_NOT_FOUND"


async def test_edit_sold_lot_409(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    lot = await _create_lot(client, access)
    fake_db["market_lots"][lot["id"]]["status"] = "sold"

    resp = await client.put(
        f"/v1/market/lots/{lot['id']}",
        json=LOT_BODY,
        headers=_auth_header(access),
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "LOT_NOT_EDITABLE"

    resp = await client.delete(f"/v1/market/lots/{lot['id']}", headers=_auth_header(access))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "LOT_NOT_EDITABLE"
