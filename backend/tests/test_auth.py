import firebase_admin.auth as fb_auth


async def test_firebase_verify_new_user(client, fake_firebase, fake_users):
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["isNewUser"] is True
    assert body["accessToken"]
    assert body["refreshToken"]
    assert body["user"]["phone"] == "+919812345678"
    assert "mpinHash" not in body["user"]


async def test_firebase_verify_invalid_token(client, monkeypatch, fake_users):
    def raise_invalid(token):
        raise fb_auth.InvalidIdTokenError("bad")

    monkeypatch.setattr(fb_auth, "verify_id_token", raise_invalid)
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_FIREBASE_TOKEN"


async def test_firebase_verify_existing_user(client, fake_firebase, fake_users):
    await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    assert resp.json()["isNewUser"] is False


async def test_refresh_roundtrip(client, fake_firebase, fake_users):
    verify_resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    refresh_token = verify_resp.json()["refreshToken"]
    resp = await client.post("/v1/auth/refresh", json={"refreshToken": refresh_token})
    assert resp.status_code == 200
    body = resp.json()
    assert body["accessToken"]
    assert body["refreshToken"]


async def test_refresh_with_access_token_fails(client, fake_firebase, fake_users):
    verify_resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    access_token = verify_resp.json()["accessToken"]
    resp = await client.post("/v1/auth/refresh", json={"refreshToken": access_token})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_TOKEN"
