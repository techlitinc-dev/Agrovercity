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


async def _register(client, **overrides) -> dict:
    await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    resp = await client.post("/v1/auth/register", json={**REGISTER_BODY, **overrides})
    assert resp.status_code == 200
    return resp.json()


async def test_register_transport_variant(client, fake_firebase, fake_users):
    body = await _register(
        client,
        profiles=["farmer", "transport"],
        roleProfiles={"transport": {"vehicleType": "Tata Ace", "rcNumber": "MH15AB1234"}},
    )
    resp = await client.get("/v1/users/me", headers=_auth_header(body["accessToken"]))
    assert resp.status_code == 200
    assert resp.json()["roleProfiles"]["transport"]["rcNumber"] == "MH15AB1234"


async def test_register_seller_variant_optionals(client, fake_firebase, fake_users):
    body = await _register(
        client,
        profiles=["farmer", "seller"],
        roleProfiles={"seller": {"shopName": "Ramesh Traders"}},
    )
    resp = await client.get("/v1/users/me", headers=_auth_header(body["accessToken"]))
    seller = resp.json()["roleProfiles"]["seller"]
    assert seller["shopName"] == "Ramesh Traders"
    assert "gstNumber" not in seller
    assert "apmcLicense" not in seller


async def test_register_variant_missing_required(client, fake_firebase, fake_users):
    resp = await client.post(
        "/v1/auth/register",
        json={**REGISTER_BODY, "profiles": ["farmer", "transport"], "roleProfiles": {"transport": {"vehicleType": "Tata Ace"}}},
    )
    assert resp.status_code == 422
    error = resp.json()["error"]
    assert error["code"] == "INVALID_ROLE_PROFILE"
    assert "transport" in error["fieldErrors"]


async def test_register_roleprofile_not_in_profiles(client, fake_firebase, fake_users):
    resp = await client.post(
        "/v1/auth/register",
        json={**REGISTER_BODY, "roleProfiles": {"broker": {"marketsServed": ["Nashik"]}}},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_ROLE_PROFILE"


async def test_register_landlord_and_broker_variants(client, fake_firebase, fake_users):
    body = await _register(
        client,
        profiles=["farmLandlord", "broker"],
        primaryProfile="farmLandlord",
        roleProfiles={
            "farmLandlord": {"totalLandAcres": 12.5},
            "broker": {"marketsServed": ["Nashik", "Lasalgaon"]},
        },
    )
    resp = await client.get("/v1/users/me", headers=_auth_header(body["accessToken"]))
    role_profiles = resp.json()["roleProfiles"]
    assert role_profiles["farmLandlord"]["totalLandAcres"] == 12.5
    assert role_profiles["broker"]["marketsServed"] == ["Nashik", "Lasalgaon"]
