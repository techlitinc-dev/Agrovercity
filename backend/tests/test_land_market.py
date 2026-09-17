from app.services.tokens import create_access_token


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users, uid, profile, phone="+919812345678", name="Ramesh") -> str:
    if uid == "uid-1":
        resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
        assert resp.status_code == 200
        fake_users["users"]["uid-1"]["activeProfile"] = profile
        fake_users["users"]["uid-1"]["id"] = "uid-1"
        return resp.json()["accessToken"]
    fake_users["users"][uid] = {"id": uid, "activeProfile": profile, "linkedProfiles": [profile], "referralCode": f"ref_{uid[:8]}", "name": name, "phone": phone}
    return create_access_token(uid)


LISTING_BODY = {
    "village": "Ozark",
    "district": "Nashik",
    "lat": 20.0,
    "lng": 73.8,
    "areaAcres": 5.0,
    "expectedRentRupees": 12000,
    "soilType": "Black Cotton",
}


async def test_create_and_browse_near_filter(client, fake_firebase, fake_users, fake_db):
    landlord = await _login(client, fake_users, "uid-2", "farmLandlord", name="Landlord L")
    await client.post("/v1/land/listings", json=LISTING_BODY, headers=_auth_header(landlord))
    await client.post(
        "/v1/land/listings",
        json={**LISTING_BODY, "village": "Far Village", "lat": 20.9, "lng": 74.7},
        headers=_auth_header(landlord),
    )
    farmer = await _login(client, fake_users, "uid-1", "farmer")

    resp = await client.get("/v1/land/listings", params={"near": "20.0,73.8"}, headers=_auth_header(farmer))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["village"] == "Ozark"


async def test_duplicate_request_409(client, fake_firebase, fake_users, fake_db):
    landlord = await _login(client, fake_users, "uid-2", "farmLandlord")
    resp = await client.post("/v1/land/listings", json=LISTING_BODY, headers=_auth_header(landlord))
    listing_id = resp.json()["id"]
    farmer = await _login(client, fake_users, "uid-1", "farmer")

    body = {"listingId": listing_id, "durationMonths": 6, "message": "Interested"}
    resp = await client.post("/v1/land/lease-requests", json=body, headers=_auth_header(farmer))
    assert resp.status_code == 201
    resp = await client.post("/v1/land/lease-requests", json=body, headers=_auth_header(farmer))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "DUPLICATE_LEASE_REQUEST"


async def test_accept_creates_lease_and_flips_listing(client, fake_firebase, fake_users, fake_db):
    landlord = await _login(client, fake_users, "uid-2", "farmLandlord", phone="+919822211122", name="Landlord L")
    resp = await client.post("/v1/land/listings", json=LISTING_BODY, headers=_auth_header(landlord))
    listing_id = resp.json()["id"]

    farmer1 = await _login(client, fake_users, "uid-1", "farmer")
    farmer2 = await _login(client, fake_users, "uid-3", "farmer", phone="+919833334444")
    r1 = (await client.post("/v1/land/lease-requests", json={"listingId": listing_id, "durationMonths": 6}, headers=_auth_header(farmer1))).json()
    r2 = (await client.post("/v1/land/lease-requests", json={"listingId": listing_id, "durationMonths": 12}, headers=_auth_header(farmer2))).json()

    resp = await client.post(f"/v1/land/lease-requests/{r1['id']}/accept", headers=_auth_header(landlord))
    assert resp.status_code == 200
    lease_id = resp.json()["leaseId"]

    listing = fake_db["land_listings"][listing_id]
    assert listing["status"] == "leased"
    assert fake_db["lease_requests"][r2["id"]]["status"] == "rejected"

    leases = (await client.get("/v1/land/leases", headers=_auth_header(landlord))).json()["data"]
    assert any(l["id"] == lease_id for l in leases)
    _ = farmer2


async def test_non_owner_accept_403(client, fake_firebase, fake_users, fake_db):
    landlord = await _login(client, fake_users, "uid-2", "farmLandlord")
    resp = await client.post("/v1/land/listings", json=LISTING_BODY, headers=_auth_header(landlord))
    listing_id = resp.json()["id"]
    farmer = await _login(client, fake_users, "uid-1", "farmer")
    request_id = (
        await client.post("/v1/land/lease-requests", json={"listingId": listing_id, "durationMonths": 6}, headers=_auth_header(farmer))
    ).json()["id"]

    other_landlord = await _login(client, fake_users, "uid-3", "farmLandlord")
    resp = await client.post(f"/v1/land/lease-requests/{request_id}/accept", headers=_auth_header(other_landlord))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "NOT_LISTING_OWNER"


async def test_agreement_pdf_returns_url(client, fake_firebase, fake_users, fake_db, monkeypatch):
    from app.services import reports as reports_service

    def fake_upload(local_path, dest_path):
        return "https://storage.example/agreement.pdf"

    monkeypatch.setattr(reports_service, "upload_to_storage", fake_upload)

    landlord = await _login(client, fake_users, "uid-2", "farmLandlord", phone="+919822211122", name="Landlord L")
    resp = await client.post("/v1/land/listings", json=LISTING_BODY, headers=_auth_header(landlord))
    listing_id = resp.json()["id"]
    farmer = await _login(client, fake_users, "uid-1", "farmer")
    request_id = (
        await client.post("/v1/land/lease-requests", json={"listingId": listing_id, "durationMonths": 6}, headers=_auth_header(farmer))
    ).json()["id"]
    lease_id = (
        await client.post(f"/v1/land/lease-requests/{request_id}/accept", headers=_auth_header(landlord))
    ).json()["leaseId"]

    resp = await client.get(f"/v1/land/leases/{lease_id}/agreement-pdf", headers=_auth_header(landlord))
    assert resp.status_code == 200
    assert resp.json()["agreementUrl"] == "https://storage.example/agreement.pdf"


async def test_tenant_can_fetch_agreement(client, fake_firebase, fake_users, fake_db):
    landlord = await _login(client, fake_users, "uid-2", "farmLandlord", phone="+919822211122", name="Landlord L")
    resp = await client.post("/v1/land/listings", json=LISTING_BODY, headers=_auth_header(landlord))
    listing_id = resp.json()["id"]
    farmer = await _login(client, fake_users, "uid-1", "farmer")
    request_id = (
        await client.post("/v1/land/lease-requests", json={"listingId": listing_id, "durationMonths": 6}, headers=_auth_header(farmer))
    ).json()["id"]
    lease_id = (
        await client.post(f"/v1/land/lease-requests/{request_id}/accept", headers=_auth_header(landlord))
    ).json()["leaseId"]

    resp = await client.get(f"/v1/land/leases/{lease_id}/agreement-pdf", headers=_auth_header(farmer))
    assert resp.status_code == 200

    outsider = await _login(client, fake_users, "uid-4", "farmLandlord", phone="+919899990000")
    resp = await client.get(f"/v1/land/leases/{lease_id}/agreement-pdf", headers=_auth_header(outsider))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "LEASE_NOT_FOUND"
