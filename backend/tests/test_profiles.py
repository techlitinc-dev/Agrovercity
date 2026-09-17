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
    "crops": ["onion"],
    "mpin": "1234",
    "profiles": ["farmer"],
    "primaryProfile": "farmer",
}


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login_and_register(client) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    access = resp.json()["accessToken"]
    resp = await client.post("/v1/auth/register", json=REGISTER_BODY)
    assert resp.status_code == 200
    return resp.json()["accessToken"]


async def test_link_profile(client, fake_firebase, fake_users):
    access = await _login_and_register(client)
    resp = await client.post("/v1/users/me/profiles", json={"profileType": "transport"}, headers=_auth_header(access))
    assert resp.status_code == 200
    assert "transport" in resp.json()["linkedProfiles"]


async def test_link_duplicate(client, fake_firebase, fake_users):
    access = await _login_and_register(client)
    resp = await client.post("/v1/users/me/profiles", json={"profileType": "transport"}, headers=_auth_header(access))
    assert resp.status_code == 200
    resp = await client.post("/v1/users/me/profiles", json={"profileType": "transport"}, headers=_auth_header(access))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "PROFILE_ALREADY_LINKED"


async def test_unlink_last_profile_blocked(client, fake_firebase, fake_users):
    access = await _login_and_register(client)
    resp = await client.delete("/v1/users/me/profiles/farmer", headers=_auth_header(access))
    assert resp.status_code == 409
    error = resp.json()["error"]
    assert error["code"] == "LAST_PROFILE"
    assert "कम से कम एक प्रोफाइल" in error["message"]


async def test_activate_returns_default_home(client, fake_firebase, fake_users):
    access = await _login_and_register(client)
    resp = await client.post("/v1/users/me/profiles", json={"profileType": "transport"}, headers=_auth_header(access))
    assert resp.status_code == 200
    resp = await client.post("/v1/users/me/profiles/transport/activate", headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["activeProfile"] == "transport"
    assert body["defaultHomeRoute"] == "transportHome"


async def test_unlink_active_promotes_primary(client, fake_firebase, fake_users):
    access = await _login_and_register(client)
    resp = await client.post("/v1/users/me/profiles", json={"profileType": "seller"}, headers=_auth_header(access))
    assert resp.status_code == 200
    resp = await client.post("/v1/users/me/profiles/seller/activate", headers=_auth_header(access))
    assert resp.status_code == 200
    resp = await client.delete("/v1/users/me/profiles/seller", headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["activeProfile"] == "farmer"
    assert body["primaryProfile"] == "farmer"


async def test_primary_star(client, fake_firebase, fake_users):
    access = await _login_and_register(client)
    resp = await client.post("/v1/users/me/profiles", json={"profileType": "seller"}, headers=_auth_header(access))
    assert resp.status_code == 200
    resp = await client.put("/v1/users/me/profiles/seller/primary", headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json()["primaryProfile"] == "seller"
