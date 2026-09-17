REGISTER_BODY = {
    "idToken": "x",
    "name": "Ramesh",
    "phone": "+919812345678",
    "state": "Maharashtra",
    "district": "Nashik",
    "tehsil": "Dindori",
    "village": "Ozark",
    "landAreaAcres": 5.5,
    "soilType": "Black Cotton",
    "irrigationType": "Drip",
    "crops": ["onion", "grapes"],
    "mpin": "1234",
    "profiles": ["farmer", "seller"],
    "primaryProfile": "farmer",
}


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    return resp.json()["accessToken"]


async def test_register_creates_full_profile(client, fake_firebase, fake_users):
    await _login(client)
    resp = await client.post("/v1/auth/register", json=REGISTER_BODY)
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["linkedProfiles"] == ["farmer", "seller"]
    assert body["user"]["activeProfile"] == "farmer"
    assert body["user"]["activeCrops"] == ["onion", "grapes"]
    assert body["accessToken"]
    assert body["refreshToken"]


async def test_register_rejects_primary_not_in_profiles(client, fake_firebase, fake_users):
    body = {**REGISTER_BODY, "primaryProfile": "broker"}
    resp = await client.post("/v1/auth/register", json=body)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_PROFILE_TYPE"


async def test_get_me(client, fake_firebase, fake_users):
    access = await _login(client)
    resp = await client.get("/v1/users/me", headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert "kisanCreditScore" in body
    assert "agriCoins" in body


async def test_put_me_partial_update(client, fake_firebase, fake_users):
    access = await _login(client)
    resp = await client.put("/v1/users/me", json={"village": "Ozark"}, headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json()["village"] == "Ozark"
    assert resp.json()["name"] == ""


async def test_farm_boundary(client, fake_firebase, fake_users):
    access = await _login(client)
    points = [
        {"lat": 20.0, "lng": 74.0},
        {"lat": 20.01, "lng": 74.0},
        {"lat": 20.01, "lng": 74.01},
        {"lat": 20.0, "lng": 74.01},
    ]
    resp = await client.put(
        "/v1/users/me/farm-boundary",
        json={"farmBoundaryPoints": points, "landAreaAcres": 5.5, "khasraNumber": "123/4"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    assert len(resp.json()["farmBoundaryPoints"]) == 4

    resp = await client.get("/v1/users/me", headers=_auth_header(access))
    assert resp.json()["farmBoundaryPoints"] == points
    assert resp.json()["landAreaAcres"] == 5.5
    assert resp.json()["khasraNumber"] == "123/4"


async def test_me_requires_auth(client, fake_firebase, fake_users):
    resp = await client.get("/v1/users/me")
    assert resp.status_code == 401
