import pytest


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users, uid="uid-1", profile="farmer", name="Ramesh") -> str:
    if uid == "uid-1":
        resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
        assert resp.status_code == 200
        fake_users["users"]["uid-1"]["activeProfile"] = profile
        fake_users["users"]["uid-1"]["id"] = "uid-1"
        return resp.json()["accessToken"]
    fake_users["users"][uid] = {"id": uid, "activeProfile": profile, "linkedProfiles": [profile], "referralCode": f"ref_{uid[:8]}"}
    from app.services.tokens import create_access_token

    return create_access_token(uid)


async def _seed_transport_booking(fake_db, booking_id="tr-1", status="delivered", vehicle_id="veh-1"):
    fake_db["vehicles"]["veh-1"] = {"id": "veh-1", "ownerId": "uid-2"}
    fake_db["transport_bookings"][booking_id] = {
        "id": booking_id,
        "userId": "uid-1",
        "vehicleId": vehicle_id,
        "status": status,
        "date": "2026-09-10",
        "fare": 850,
    }


async def _seed_equipment_booking(client, fake_users, fake_db, booking_id="eq-1", status="booked"):
    farmer = await _login(client, fake_users)
    fake_db["equipment"]["eq-1"] = {"id": "eq-1", "ownerId": "uid-2", "docStatus": "verified", "active": True, "name": "Tractor"}
    fake_db["users/uid-1/equipment_bookings"][booking_id] = {
        "id": booking_id,
        "equipmentId": "eq-1",
        "status": status,
        "date": "2026-09-20",
        "priceRupees": 800,
    }
    return farmer


async def test_rate_delivered_transport_booking_201(client, fake_firebase, fake_users, fake_db):
    await _seed_transport_booking(fake_db)
    access = await _login(client, fake_users)

    resp = await client.post(
        "/v1/ratings",
        json={"bookingKind": "transport", "bookingId": "tr-1", "stars": 4, "comment": "on time"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 201
    assert resp.json()["providerId"] == "uid-2"
    aggregate = fake_db["provider_ratings"]["uid-2"]
    assert aggregate["ratingCount"] == 1


async def test_not_completed_409(client, fake_firebase, fake_users, fake_db):
    await _seed_transport_booking(fake_db, status="requested")
    access = await _login(client, fake_users)

    resp = await client.post(
        "/v1/ratings",
        json={"bookingKind": "transport", "bookingId": "tr-1", "stars": 4},
        headers=_auth_header(access),
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "NOT_COMPLETED"


async def test_double_rating_409(client, fake_firebase, fake_users, fake_db):
    await _seed_transport_booking(fake_db)
    access = await _login(client, fake_users)
    body = {"bookingKind": "transport", "bookingId": "tr-1", "stars": 4}
    assert (await client.post("/v1/ratings", json=body, headers=_auth_header(access))).status_code == 201

    resp = await client.post("/v1/ratings", json=body, headers=_auth_header(access))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ALREADY_RATED"


async def test_foreign_booking_404(client, fake_firebase, fake_users, fake_db):
    await _seed_transport_booking(fake_db)
    fake_db["transport_bookings"]["tr-1"]["userId"] = "uid-9"
    access = await _login(client, fake_users)

    resp = await client.post(
        "/v1/ratings",
        json={"bookingKind": "transport", "bookingId": "tr-1", "stars": 4},
        headers=_auth_header(access),
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "BOOKING_NOT_FOUND"


async def test_provider_list_shows_rating(client, fake_firebase, fake_users, fake_db):
    farmer = await _seed_equipment_booking(client, fake_users, fake_db, status="booked")

    resp = await client.post(
        "/v1/ratings",
        json={"bookingKind": "equipment", "bookingId": "eq-1", "stars": 4},
        headers=_auth_header(farmer),
    )
    assert resp.status_code == 201

    resp = await client.get("/v1/equipment", headers=_auth_header(farmer))
    equipment = next(e for e in resp.json()["data"] if e["id"] == "eq-1")
    assert equipment["ratingAvg"] == 4.0
    assert equipment["ratingCount"] == 1


async def test_aggregate_averages(client, fake_firebase, fake_users, fake_db):
    await _seed_transport_booking(fake_db)
    access_a = await _login(client, fake_users, "uid-1")
    body = {"bookingKind": "transport", "bookingId": "tr-1", "stars": 4}
    await client.post("/v1/ratings", json=body, headers=_auth_header(access_a))

    # second rater on a different booking for the same provider
    fake_db["transport_bookings"]["tr-2"] = {
        "id": "tr-2",
        "userId": "uid-3",
        "vehicleId": "veh-1",
        "status": "delivered",
        "date": "2026-09-11",
        "fare": 900,
    }
    fake_users["users"]["uid-3"] = {"id": "uid-3", "activeProfile": "farmer", "linkedProfiles": ["farmer"]}
    access_c = create_access_token_local("uid-3")
    resp = await client.post(
        "/v1/ratings",
        json={"bookingKind": "transport", "bookingId": "tr-2", "stars": 2},
        headers=_auth_header(access_c),
    )
    assert resp.status_code == 201
    aggregate = fake_db["provider_ratings"]["uid-2"]
    assert aggregate["ratingCount"] == 2
    assert aggregate["ratingAvg"] == 3.0


def create_access_token_local(uid: str) -> str:
    from app.services.tokens import create_access_token

    return create_access_token(uid)


async def test_provider_rating_aggregate_lookup(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    fake_db["provider_ratings"]["uid-2"] = {"ratingAvg": 4.5, "ratingCount": 2, "updatedAt": "2026-09-17T00:00:00Z"}

    resp = await client.get("/v1/ratings/providers/uid-2", headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json() == {"ratingAvg": 4.5, "ratingCount": 2}


async def test_provider_rating_unrated_returns_zeroes(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)

    resp = await client.get("/v1/ratings/providers/uid-42", headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json() == {"ratingAvg": None, "ratingCount": 0}
