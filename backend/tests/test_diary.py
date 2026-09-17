def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


DIARY_BODY = {
    "title": "Urea 1 bag",
    "category": "fertilizer",
    "type": "expense",
    "amount": 450,
    "date": "2026-09-13",
    "cropName": "Wheat",
}


async def _login(client, fake_users, fake_db, profile="farmer") -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    fake_users["users"]["uid-1"]["activeProfile"] = profile
    fake_users["users"]["uid-1"]["id"] = "uid-1"
    fake_db["users"]["uid-1"] = {"id": "uid-1", "agriCoins": 0}
    return resp.json()["accessToken"]


async def test_create_entry_awards_15_coins(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db)
    resp = await client.post("/v1/diary/entries", json=DIARY_BODY, headers=_auth_header(access))
    assert resp.status_code == 201
    body = resp.json()
    assert body["agriCoinsEarned"] == 15
    assert body["entry"]["id"]
    assert fake_db["users"]["uid-1"]["agriCoins"] == 15
    ledger = list(fake_db["users/uid-1/coin_ledger"].values())
    assert ledger[0]["reason"] == "diary_entry"


async def test_list_filters_by_type(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db)
    await client.post("/v1/diary/entries", json=DIARY_BODY, headers=_auth_header(access))
    await client.post(
        "/v1/diary/entries",
        json={"title": "Tomato sale", "category": "sale", "type": "income", "amount": 9000, "date": "2026-09-14"},
        headers=_auth_header(access),
    )
    resp = await client.get("/v1/diary/entries", params={"type": "expense"}, headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["data"][0]["type"] == "expense"


async def test_delete_entry(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db)
    resp = await client.post("/v1/diary/entries", json=DIARY_BODY, headers=_auth_header(access))
    entry_id = resp.json()["entry"]["id"]

    resp = await client.delete(f"/v1/diary/entries/{entry_id}", headers=_auth_header(access))
    assert resp.status_code == 204
    assert fake_db["users/uid-1/diary_entries"] == {}

    resp = await client.delete(f"/v1/diary/entries/{entry_id}", headers=_auth_header(access))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "ENTRY_NOT_FOUND"


async def test_report_returns_url(client, fake_firebase, fake_users, fake_db, monkeypatch):
    from app.services import reports as reports_service

    def fake_upload(local_path, dest_path):
        return "https://storage.example/x.pdf"

    monkeypatch.setattr(reports_service, "upload_to_storage", fake_upload)
    access = await _login(client, fake_users, fake_db)
    await client.post("/v1/diary/entries", json=DIARY_BODY, headers=_auth_header(access))

    resp = await client.get("/v1/diary/report", params={"from": "2026-09-01", "to": "2026-09-30"}, headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["reportUrl"] == "https://storage.example/x.pdf"
    assert body["entryCount"] == 1


async def test_forbidden_for_seller(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db, profile="seller")
    resp = await client.get("/v1/diary/entries", headers=_auth_header(access))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN_ROLE"
