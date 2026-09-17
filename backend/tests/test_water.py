def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users, crops=None) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    fake_users["users"]["uid-1"]["activeProfile"] = "farmer"
    fake_users["users"]["uid-1"]["id"] = "uid-1"
    if crops is not None:
        fake_users["users"]["uid-1"]["activeCrops"] = crops
    return resp.json()["accessToken"]


async def test_schedule_one_entry_per_crop(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, crops=["Wheat", "Onion"])
    resp = await client.get("/v1/water/schedule", headers=_auth_header(access))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 2
    assert all(e["recommendedMinutes"] in {30, 90} for e in data)
    resp2 = await client.get("/v1/water/schedule", headers=_auth_header(access))
    assert resp2.json()["data"] == data


async def test_groundwater_requires_district(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.get("/v1/water/groundwater", headers=_auth_header(access))
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "MISSING_DISTRICT"


async def test_groundwater_nagpur_critical(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.get("/v1/water/groundwater", params={"district": "Nagpur"}, headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json()["zone"] == "critical"


async def test_canal_rotation_filter(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.get("/v1/water/canal-rotation", params={"canal": "gangapur"}, headers=_auth_header(access))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["canalName"] == "Gangapur Canal"


async def test_pmksy_exact(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.post("/v1/water/pmksy-calculator", json={"acres": 2}, headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json() == {"totalCost": 170000, "subsidyPercent": 55, "subsidyAmount": 93500.0, "farmerShare": 76500.0}
