from scripts.seed_mandi import MANDI_PRICES, MANDIS


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    return resp.json()["accessToken"]


async def test_prices_returns_all(client, fake_firebase, fake_users, fake_db):
    for doc in MANDI_PRICES:
        fake_db["mandi_prices"][doc["id"]] = doc
    access = await _login(client, fake_users)
    resp = await client.get("/v1/mandi/prices", headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 4
    assert body["total"] == 4
    assert body["page"] == 1
    assert body["pageSize"] == 20


async def test_prices_crop_filter_tomato(client, fake_firebase, fake_users, fake_db):
    for doc in MANDI_PRICES:
        fake_db["mandi_prices"][doc["id"]] = doc
    access = await _login(client, fake_users)
    resp = await client.get("/v1/mandi/prices", params={"crop": "tomato"}, headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 3
    assert all("Onion" not in d["commodity"] for d in body["data"])


async def test_prices_forbidden_role(client, fake_firebase, fake_users, fake_db):
    for doc in MANDI_PRICES:
        fake_db["mandi_prices"][doc["id"]] = doc
    access = await _login(client, fake_users)
    fake_users["users"]["uid-1"]["activeProfile"] = "transport"
    resp = await client.get("/v1/mandi/prices", headers=_auth_header(access))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN_ROLE"


async def test_mandi_list(client, fake_firebase, fake_users, fake_db):
    for doc in MANDIS:
        fake_db["mandis"][doc["id"]] = doc
    access = await _login(client, fake_users)
    resp = await client.get("/v1/mandi/list", headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 4
    assert all(d["name"] for d in body["data"])
