def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    return resp.json()["accessToken"]


async def test_set_and_verify_mpin(client, fake_firebase, fake_users):
    access = await _login(client)
    resp = await client.post("/v1/auth/mpin/set", json={"mpin": "1234"}, headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    resp = await client.post("/v1/auth/mpin/verify", json={"mpin": "1234"}, headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


async def test_verify_wrong_mpin(client, fake_firebase, fake_users):
    access = await _login(client)
    await client.post("/v1/auth/mpin/set", json={"mpin": "1234"}, headers=_auth_header(access))
    resp = await client.post("/v1/auth/mpin/verify", json={"mpin": "9999"}, headers=_auth_header(access))
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "WRONG_MPIN"


async def test_verify_before_set(client, fake_firebase, fake_users):
    access = await _login(client)
    resp = await client.post("/v1/auth/mpin/verify", json={"mpin": "1234"}, headers=_auth_header(access))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "MPIN_NOT_SET"


async def test_set_bad_format(client, fake_firebase, fake_users):
    access = await _login(client)
    resp = await client.post("/v1/auth/mpin/set", json={"mpin": "12ab"}, headers=_auth_header(access))
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_MPIN_FORMAT"


async def test_reset_with_firebase_token(client, fake_firebase, fake_users):
    access = await _login(client)
    await client.post("/v1/auth/mpin/set", json={"mpin": "1234"}, headers=_auth_header(access))

    resp = await client.post("/v1/auth/mpin/reset", json={"idToken": "x", "newMpin": "4321"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    resp = await client.post("/v1/auth/mpin/verify", json={"mpin": "1234"}, headers=_auth_header(access))
    assert resp.status_code == 401

    resp = await client.post("/v1/auth/mpin/verify", json={"mpin": "4321"}, headers=_auth_header(access))
    assert resp.status_code == 200
