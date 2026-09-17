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

REFERRER_CODE = "ref_ab12cd34"


async def _preverify(client):
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200


async def test_register_with_valid_referral(client, fake_firebase, fake_users):
    fake_users["users"]["uid-2"] = {"id": "uid-2", "phone": "+919876543210", "referralCode": REFERRER_CODE}
    await _preverify(client)
    resp = await client.post("/v1/auth/register", json={**REGISTER_BODY, "referralCode": REFERRER_CODE})
    assert resp.status_code == 200
    body = resp.json()
    assert body["referral"]["applied"] is True
    attribution = fake_users["referral_attributions"]["uid-1"]
    assert attribution["referrerUid"] == "uid-2"
    assert attribution["referredUid"] == "uid-1"
    assert attribution["status"] == "pending"


async def test_register_invalid_referral_code(client, fake_firebase, fake_users):
    await _preverify(client)
    resp = await client.post("/v1/auth/register", json={**REGISTER_BODY, "referralCode": "ref_nope123"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_REFERRAL_CODE"


async def test_register_without_referral(client, fake_firebase, fake_users):
    await _preverify(client)
    resp = await client.post("/v1/auth/register", json=REGISTER_BODY)
    assert resp.status_code == 200
    assert resp.json()["referral"]["applied"] is False
    assert len(fake_users["referral_attributions"]) == 0


async def test_register_self_referral(client, fake_firebase, fake_users):
    await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    own_code = "ref_uid-1"
    resp = await client.post("/v1/auth/register", json={**REGISTER_BODY, "referralCode": own_code})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_REFERRAL_CODE"
