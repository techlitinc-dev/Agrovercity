def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users, fake_db) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    fake_users["users"]["uid-1"]["activeProfile"] = "farmer"
    fake_users["users"]["uid-1"]["id"] = "uid-1"
    fake_db["users"]["uid-1"] = {"id": "uid-1", "landAreaAcres": 0}
    return resp.json()["accessToken"]


async def test_search_by_village_fuzzy(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db)
    resp = await client.get("/v1/land-records/search", params={"village": "Ozar"}, headers=_auth_header(access))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) >= 1
    assert any(r["village"] == "Ozarkhed" for r in data)


async def test_village_too_short_422(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db)
    resp = await client.get("/v1/land-records/search", params={"village": "Oz"}, headers=_auth_header(access))
    assert resp.status_code == 422


async def test_search_by_gat_exact(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db)
    resp = await client.get("/v1/land-records/search", params={"gatNumber": "123"}, headers=_auth_header(access))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["id"] == "rec-1"


async def test_missing_params_400(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db)
    resp = await client.get("/v1/land-records/search", headers=_auth_header(access))
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "MISSING_SEARCH_PARAM"


async def test_import_updates_profile(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db)
    resp = await client.post("/v1/land-records/rec-1/import", headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"imported": True, "landAreaAcres": 2.97}
    user_doc = fake_db["users"]["uid-1"]
    assert user_doc["landAreaAcres"] == 2.97
    assert any(r["gatNumber"] == "123" for r in user_doc["landRecords"])


async def test_adapter_swap_env(client, fake_firebase, fake_users, fake_db, monkeypatch):
    from app.services.land_records import get_adapter
    from app.services.land_records.mock_adapter import MockAdapter

    monkeypatch.setenv("LAND_RECORDS_ADAPTER", "mock")
    assert isinstance(get_adapter(), MockAdapter)
