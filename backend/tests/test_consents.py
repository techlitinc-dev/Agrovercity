def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    fake_users["users"]["uid-1"]["activeProfile"] = "farmer"
    fake_users["users"]["uid-1"]["id"] = "uid-1"
    return resp.json()["accessToken"]


async def test_defaults_all_false(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.get("/v1/users/me/consents", headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["dataSharing"] is False
    assert body["location"] is False
    assert body["marketing"] is False


async def test_put_round_trip(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    body = {"dataSharing": True, "location": True, "marketing": False}
    resp = await client.put("/v1/users/me/consents", json=body, headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json()["updatedAt"]

    resp = await client.get("/v1/users/me/consents", headers=_auth_header(access))
    body_back = resp.json()
    assert body_back["dataSharing"] is True
    assert body_back["location"] is True
    assert body_back["marketing"] is False


async def test_consent_log_appended_per_change(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    await client.put(
        "/v1/users/me/consents",
        json={"dataSharing": True, "location": False, "marketing": False},
        headers=_auth_header(access),
    )
    await client.put(
        "/v1/users/me/consents",
        json={"dataSharing": True, "location": True, "marketing": True},
        headers=_auth_header(access),
    )
    log_docs = [d for d in fake_db["consent_log"].values() if d["userId"] == "uid-1"]
    assert len(log_docs) == 3
    assert all({"flag", "newValue", "at"} <= set(d) for d in log_docs)


async def test_put_missing_flag_422(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.put(
        "/v1/users/me/consents",
        json={"dataSharing": True, "location": True},
        headers=_auth_header(access),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_require_data_sharing_raises_when_off(client, fake_firebase, fake_users, fake_db):
    import pytest

    from app.models.consents import ConsentRequiredError
    from app.services import consents as consents_service

    access = await _login(client, fake_users)
    with pytest.raises(ConsentRequiredError):
        await consents_service.require_data_sharing("uid-1")

    await client.put(
        "/v1/users/me/consents",
        json={"dataSharing": True, "location": False, "marketing": False},
        headers=_auth_header(access),
    )
    await consents_service.require_data_sharing("uid-1")
