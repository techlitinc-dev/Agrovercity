from app.services.tokens import create_access_token


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _setup(client, fake_users, fake_db) -> tuple[str, str, str]:
    """Returns (farmer_token, transporter_token, booking_id)."""
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    farmer = resp.json()["accessToken"]
    fake_users["users"]["uid-1"]["activeProfile"] = "farmer"
    fake_users["users"]["uid-1"]["id"] = "uid-1"

    fake_users["users"]["uid-2"] = {"id": "uid-2", "activeProfile": "transport", "linkedProfiles": ["transport"], "referralCode": "ref_uid-2"}
    transporter = create_access_token("uid-2")

    resp = await client.post(
        "/v1/transport/vehicles",
        json={"vehicleType": "Tata Ace", "registrationNo": "MH15AB1234", "capacityTonnes": 0.75},
        headers=_auth_header(transporter),
    )
    vehicle_id = resp.json()["id"]
    fake_db["vehicles"][vehicle_id]["docStatus"] = "verified"

    resp = await client.post(
        "/v1/transport/bookings",
        json={"vehicleType": "Tata Ace", "distanceKm": 10, "pickup": "Ozark", "drop": "Nashik Mandi", "date": "2026-09-20"},
        headers=_auth_header(farmer),
    )
    booking_id = resp.json()["id"]
    return farmer, transporter, booking_id


async def test_accept_requested_booking(client, fake_firebase, fake_users, fake_db):
    farmer, transporter, booking_id = await _setup(client, fake_users, fake_db)
    vehicle_id = fake_db["vehicles"] and next(iter(fake_db["vehicles"]))

    resp = await client.post(
        f"/v1/transport/bookings/{booking_id}/accept",
        json={"vehicleId": vehicle_id, "vehicleNo": "MH15AB1234"},
        headers=_auth_header(transporter),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"

    notifications = [d for d in fake_db["notifications"].values() if d["userId"] == "uid-1"]
    assert any(n["data"]["type"] == "booking_accepted" for n in notifications)


async def test_accept_non_requested_409(client, fake_firebase, fake_users, fake_db):
    farmer, transporter, booking_id = await _setup(client, fake_users, fake_db)
    vehicle_id = next(iter(fake_db["vehicles"]))
    await client.post(
        f"/v1/transport/bookings/{booking_id}/accept",
        json={"vehicleId": vehicle_id},
        headers=_auth_header(transporter),
    )

    resp = await client.post(f"/v1/transport/bookings/{booking_id}/accept", json={}, headers=_auth_header(transporter))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ILLEGAL_TRANSITION"


async def test_reject_with_reason(client, fake_firebase, fake_users, fake_db):
    farmer, transporter, booking_id = await _setup(client, fake_users, fake_db)

    resp = await client.post(
        f"/v1/transport/bookings/{booking_id}/reject",
        json={"reason": "वाहन उपलब्ध नहीं"},
        headers=_auth_header(transporter),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cancelled"
    assert body["cancellationReason"] == "वाहन उपलब्ध नहीं"
    assert body["cancelledBy"] == "transporter"

    notifications = [d for d in fake_db["notifications"].values() if d["userId"] == "uid-1"]
    assert any("वाहन उपलब्ध नहीं" in n["body"] for n in notifications)


async def test_reject_without_reason_422(client, fake_firebase, fake_users, fake_db):
    farmer, transporter, booking_id = await _setup(client, fake_users, fake_db)

    resp = await client.post(f"/v1/transport/bookings/{booking_id}/reject", json={"reason": "ab"}, headers=_auth_header(transporter))
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_farmer_cannot_accept_403(client, fake_firebase, fake_users, fake_db):
    farmer, transporter, booking_id = await _setup(client, fake_users, fake_db)

    resp = await client.post(f"/v1/transport/bookings/{booking_id}/accept", json={}, headers=_auth_header(farmer))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN_ROLE"
