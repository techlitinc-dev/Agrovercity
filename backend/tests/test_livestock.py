from app.data.livestock_seed import seed_livestock


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users, uid="uid-1", profile="farmer") -> str:
    if uid == "uid-1":
        resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
        assert resp.status_code == 200
        fake_users["users"]["uid-1"]["activeProfile"] = profile
        fake_users["users"]["uid-1"]["id"] = "uid-1"
        return resp.json()["accessToken"]
    fake_users["users"][uid] = {"id": uid, "activeProfile": profile, "linkedProfiles": [profile], "referralCode": f"ref_{uid[:8]}"}
    from app.services.tokens import create_access_token

    return create_access_token(uid)


async def test_gaushalas_by_district(client, fake_firebase, fake_users, fake_db):
    await seed_livestock()
    access = await _login(client, fake_users)
    resp = await client.get("/v1/gaushalas", params={"district": "Nashik"}, headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json()["total"] == 3


async def test_manure_order_201(client, fake_firebase, fake_users, fake_db):
    await seed_livestock()
    access = await _login(client, fake_users)
    resp = await client.post(
        "/v1/gaushalas/gau-1/manure-order",
        json={"product": "गोबर खाद", "quantity": "2 ट्रक"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "placed"
    assert "users/uid-1/manure_orders" in fake_db


async def test_vets_emergency_filter(client, fake_firebase, fake_users, fake_db):
    await seed_livestock()
    access = await _login(client, fake_users)
    resp = await client.get("/v1/vets", params={"emergency": "true"}, headers=_auth_header(access))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 2
    distances = [v["distanceKm"] for v in data]
    assert distances == sorted(distances)
    assert all(v["emergencyAvailable"] for v in data)


async def test_farm_visit_unavailable_400(client, fake_firebase, fake_users, fake_db):
    await seed_livestock()
    access = await _login(client, fake_users)
    resp = await client.post(
        "/v1/vets/vet-3/book",
        json={"visitType": "farm", "slot": "2026-09-20 09:00", "animalType": "गाय"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "FARM_VISIT_UNAVAILABLE"


async def test_vet_booking_visible_in_my_bookings(client, fake_firebase, fake_users, fake_db):
    await seed_livestock()
    access = await _login(client, fake_users)
    booking = (
        await client.post(
            "/v1/vets/vet-1/book",
            json={"visitType": "farm", "slot": "2026-09-18 09:00", "animalType": "गाय"},
            headers=_auth_header(access),
        )
    ).json()
    assert booking["status"] == "confirmed"
    assert booking["consultationFeeRupees"] == 500

    bookings = (await client.get("/v1/users/me/bookings", headers=_auth_header(access))).json()
    assert len(bookings["vet"]) == 1
    assert bookings["vet"][0]["kind"] == "vet"
    assert bookings["vet"][0]["vetName"] == "Dr. Sanjay More"


async def test_dairy_order_out_of_stock_409(client, fake_firebase, fake_users, fake_db):
    await seed_livestock()
    access = await _login(client, fake_users)
    resp = await client.post("/v1/dairy-products/dairy-4/order", json={"quantity": 1}, headers=_auth_header(access))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "OUT_OF_STOCK"


async def test_dairy_order_total(client, fake_firebase, fake_users, fake_db):
    await seed_livestock()
    access = await _login(client, fake_users)
    resp = await client.post("/v1/dairy-products/dairy-3/order", json={"quantity": 2}, headers=_auth_header(access))
    assert resp.status_code == 201
    assert resp.json() == {"orderId": resp.json()["orderId"], "total": 900}
