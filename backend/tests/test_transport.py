from app.services.tokens import create_access_token


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
    return create_access_token(uid)


async def _create_vehicle(client, access, registration_no="MH15AB1234", **overrides) -> dict:
    resp = await client.post(
        "/v1/transport/vehicles",
        json={"vehicleType": "Tata Ace", "registrationNo": registration_no, "capacityTonnes": 0.75, **overrides},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    return resp.json()


async def test_vehicle_types(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.get("/v1/transport/vehicles", headers=_auth_header(access))
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 3


async def test_fare_estimate(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.post(
        "/v1/transport/fare-estimate",
        json={"vehicleType": "Tata Ace", "distanceKm": 20},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["distanceFare"] == 700
    assert body["totalFare"] == 1200


async def test_booking_lifecycle(client, fake_firebase, fake_users, fake_db):
    farmer = await _login(client, fake_users)
    transporter = await _login(client, fake_users, uid="uid-2", profile="transport")
    vehicle = await _create_vehicle(client, transporter)
    fake_db["vehicles"][vehicle["id"]]["docStatus"] = "verified"

    resp = await client.post(
        "/v1/transport/bookings",
        json={"vehicleType": "Tata Ace", "distanceKm": 20, "pickup": "Ozark", "drop": "Nashik Mandi", "date": "2026-09-20"},
        headers=_auth_header(farmer),
    )
    assert resp.status_code == 200
    booking_id = resp.json()["id"]
    assert resp.json()["status"] == "requested"
    assert resp.json()["fare"] == 1200

    resp = await client.patch(
        f"/v1/transport/bookings/{booking_id}",
        json={"status": "accepted", "vehicleId": vehicle["id"], "vehicleNo": "MH15AB1234"},
        headers=_auth_header(transporter),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"

    resp = await client.patch(f"/v1/transport/bookings/{booking_id}", json={"status": "enRoute"}, headers=_auth_header(transporter))
    assert resp.status_code == 200

    resp = await client.patch(
        f"/v1/transport/bookings/{booking_id}",
        json={"status": "delivered", "podPhotos": ["https://storage/pod.jpg"], "receiverName": "Ramesh"},
        headers=_auth_header(transporter),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "delivered"


async def test_illegal_transition(client, fake_firebase, fake_users, fake_db):
    farmer = await _login(client, fake_users)
    transporter = await _login(client, fake_users, uid="uid-2", profile="transport")

    resp = await client.post(
        "/v1/transport/bookings",
        json={"vehicleType": "Tata Ace", "distanceKm": 10, "pickup": "A", "drop": "B", "date": "2026-09-20"},
        headers=_auth_header(farmer),
    )
    booking_id = resp.json()["id"]

    resp = await client.patch(f"/v1/transport/bookings/{booking_id}", json={"status": "delivered"}, headers=_auth_header(transporter))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ILLEGAL_TRANSITION"

    fake_db["transport_bookings"][booking_id]["status"] = "delivered"
    resp = await client.patch(f"/v1/transport/bookings/{booking_id}", json={"status": "cancelled"}, headers=_auth_header(transporter))
    assert resp.status_code == 409


async def test_owner_vehicle_crud(client, fake_firebase, fake_users, fake_db):
    transporter = await _login(client, fake_users, uid="uid-2", profile="transport")
    other = await _login(client, fake_users, uid="uid-3", profile="transport")

    vehicle = await _create_vehicle(client, transporter, registration_no="MH15AB1234")
    assert vehicle["docStatus"] == "pending"
    assert vehicle["active"] is True

    resp = await client.get("/v1/transport/vehicles/my", headers=_auth_header(transporter))
    assert any(v["id"] == vehicle["id"] for v in resp.json()["data"])

    resp = await client.put(
        f"/v1/transport/vehicles/{vehicle['id']}",
        json={"vehicleType": "Tata Ace", "registrationNo": "MH15XY9999", "capacityTonnes": 0.75},
        headers=_auth_header(transporter),
    )
    assert resp.json()["registrationNo"] == "MH15XY9999"

    resp = await client.put(
        f"/v1/transport/vehicles/{vehicle['id']}",
        json={"vehicleType": "Tata Ace", "registrationNo": "XX", "capacityTonnes": 1},
        headers=_auth_header(other),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "NOT_VEHICLE_OWNER"

    resp = await client.delete(f"/v1/transport/vehicles/{vehicle['id']}", headers=_auth_header(transporter))
    assert resp.status_code == 200
    assert fake_db["vehicles"][vehicle["id"]]["active"] is False


async def test_vehicle_calendar_and_availability(client, fake_firebase, fake_users, fake_db):
    farmer = await _login(client, fake_users)
    transporter = await _login(client, fake_users, uid="uid-2", profile="transport")
    vehicle = await _create_vehicle(client, transporter)
    fake_db["vehicles"][vehicle["id"]]["docStatus"] = "verified"

    resp = await client.post(
        "/v1/transport/bookings",
        json={"vehicleType": "Tata Ace", "distanceKm": 15, "pickup": "A", "drop": "B", "date": "2026-09-20"},
        headers=_auth_header(farmer),
    )
    booking_id = resp.json()["id"]
    await client.patch(
        f"/v1/transport/bookings/{booking_id}",
        json={"status": "accepted", "vehicleId": vehicle["id"]},
        headers=_auth_header(transporter),
    )

    resp = await client.get(f"/v1/transport/vehicles/{vehicle['id']}/calendar", headers=_auth_header(transporter))
    assert resp.status_code == 200
    calendar = resp.json()["bookings"]
    assert any(b["bookingId"] == booking_id for b in calendar)

    resp = await client.put(
        f"/v1/transport/vehicles/{vehicle['id']}/availability",
        json={"availableDates": ["2026-09-25", "2026-09-26"]},
        headers=_auth_header(transporter),
    )
    assert resp.status_code == 200
    assert resp.json()["availableDates"] == ["2026-09-25", "2026-09-26"]


async def test_new_vehicle_pending_doc_status(client, fake_firebase, fake_users, fake_db):
    transporter = await _login(client, fake_users, uid="uid-2", profile="transport")
    vehicle = await _create_vehicle(client, transporter)
    assert vehicle["docStatus"] == "pending"


async def test_accept_with_unverified_vehicle_422(client, fake_firebase, fake_users, fake_db):
    farmer = await _login(client, fake_users)
    transporter = await _login(client, fake_users, uid="uid-2", profile="transport")
    vehicle = await _create_vehicle(client, transporter)

    resp = await client.post(
        "/v1/transport/bookings",
        json={"vehicleType": "Tata Ace", "distanceKm": 10, "pickup": "A", "drop": "B", "date": "2026-09-20"},
        headers=_auth_header(farmer),
    )
    booking_id = resp.json()["id"]

    resp = await client.post(
        f"/v1/transport/bookings/{booking_id}/accept",
        json={"vehicleId": vehicle["id"]},
        headers=_auth_header(transporter),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VEHICLE_NOT_VERIFIED"


async def test_accept_with_verified_vehicle_ok(client, fake_firebase, fake_users, fake_db):
    farmer = await _login(client, fake_users)
    transporter = await _login(client, fake_users, uid="uid-2", profile="transport")
    vehicle = await _create_vehicle(client, transporter)
    fake_db["vehicles"][vehicle["id"]]["docStatus"] = "verified"

    resp = await client.post(
        "/v1/transport/bookings",
        json={"vehicleType": "Tata Ace", "distanceKm": 10, "pickup": "A", "drop": "B", "date": "2026-09-20"},
        headers=_auth_header(farmer),
    )
    booking_id = resp.json()["id"]

    resp = await client.post(
        f"/v1/transport/bookings/{booking_id}/accept",
        json={"vehicleId": vehicle["id"], "vehicleNo": "MH15AB1234"},
        headers=_auth_header(transporter),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"


async def test_verified_only_filter(client, fake_firebase, fake_users, fake_db):
    transporter = await _login(client, fake_users, uid="uid-2", profile="transport")
    v1 = await _create_vehicle(client, transporter, registration_no="MH15AA1111")
    v2 = await _create_vehicle(client, transporter, registration_no="MH15BB2222")
    fake_db["vehicles"][v2["id"]]["docStatus"] = "verified"

    resp = await client.get("/v1/transport/vehicles/my", params={"verifiedOnly": "true"}, headers=_auth_header(transporter))
    ids = [v["id"] for v in resp.json()["data"]]
    assert v2["id"] in ids
    assert v1["id"] not in ids


async def test_delivered_requires_pod(client, fake_firebase, fake_users, fake_db):
    farmer = await _login(client, fake_users)
    transporter = await _login(client, fake_users, uid="uid-2", profile="transport")
    vehicle = await _create_vehicle(client, transporter)
    fake_db["vehicles"][vehicle["id"]]["docStatus"] = "verified"
    booking_id = (
        await client.post(
            "/v1/transport/bookings",
            json={"vehicleType": "Tata Ace", "distanceKm": 10, "pickup": "A", "drop": "B", "date": "2026-09-20"},
            headers=_auth_header(farmer),
        )
    ).json()["id"]
    await client.patch(
        f"/v1/transport/bookings/{booking_id}",
        json={"status": "accepted", "vehicleId": vehicle["id"]},
        headers=_auth_header(transporter),
    )
    await client.patch(f"/v1/transport/bookings/{booking_id}", json={"status": "enRoute"}, headers=_auth_header(transporter))

    resp = await client.patch(f"/v1/transport/bookings/{booking_id}", json={"status": "delivered"}, headers=_auth_header(transporter))
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "POD_REQUIRED"
    assert "podPhotos" in body["error"]["fieldErrors"]
    assert "receiverName" in body["error"]["fieldErrors"]


async def test_delivered_with_pod(client, fake_firebase, fake_users, fake_db):
    farmer = await _login(client, fake_users)
    transporter = await _login(client, fake_users, uid="uid-2", profile="transport")
    vehicle = await _create_vehicle(client, transporter)
    fake_db["vehicles"][vehicle["id"]]["docStatus"] = "verified"
    booking_id = (
        await client.post(
            "/v1/transport/bookings",
            json={"vehicleType": "Tata Ace", "distanceKm": 10, "pickup": "A", "drop": "B", "date": "2026-09-20"},
            headers=_auth_header(farmer),
        )
    ).json()["id"]
    await client.patch(
        f"/v1/transport/bookings/{booking_id}",
        json={"status": "accepted", "vehicleId": vehicle["id"]},
        headers=_auth_header(transporter),
    )
    await client.patch(f"/v1/transport/bookings/{booking_id}", json={"status": "enRoute"}, headers=_auth_header(transporter))

    resp = await client.patch(
        f"/v1/transport/bookings/{booking_id}",
        json={"status": "delivered", "podPhotos": ["https://storage/pod.jpg"], "receiverName": "Suresh"},
        headers=_auth_header(transporter),
    )
    assert resp.status_code == 200
    assert resp.json()["pod"]["receiverName"] == "Suresh"


async def test_pod_visible_in_detail(client, fake_firebase, fake_users, fake_db):
    farmer = await _login(client, fake_users)
    transporter = await _login(client, fake_users, uid="uid-2", profile="transport")
    vehicle = await _create_vehicle(client, transporter)
    fake_db["vehicles"][vehicle["id"]]["docStatus"] = "verified"
    booking_id = (
        await client.post(
            "/v1/transport/bookings",
            json={"vehicleType": "Tata Ace", "distanceKm": 10, "pickup": "A", "drop": "B", "date": "2026-09-20"},
            headers=_auth_header(farmer),
        )
    ).json()["id"]
    await client.patch(
        f"/v1/transport/bookings/{booking_id}",
        json={"status": "accepted", "vehicleId": vehicle["id"]},
        headers=_auth_header(transporter),
    )
    await client.patch(f"/v1/transport/bookings/{booking_id}", json={"status": "enRoute"}, headers=_auth_header(transporter))
    await client.patch(
        f"/v1/transport/bookings/{booking_id}",
        json={"status": "delivered", "podPhotos": ["https://storage/pod.jpg"], "receiverName": "Suresh"},
        headers=_auth_header(transporter),
    )

    resp = await client.get("/v1/transport/bookings", headers=_auth_header(transporter))
    booking = next(b for b in resp.json()["data"] if b["id"] == booking_id)
    assert booking["pod"]["receiverName"] == "Suresh"


async def test_booking_with_own_open_lot(client, fake_firebase, fake_users, fake_db):
    farmer = await _login(client, fake_users)
    transporter = await _login(client, fake_users, uid="uid-2", profile="transport")
    fake_db["market_lots"]["lot-1"] = {
        "id": "lot-1",
        "farmerId": "uid-1",
        "crop": "Tomato",
        "quantityQuintals": 10,
        "expectedRate": 2100,
        "status": "open",
    }

    resp = await client.post(
        "/v1/transport/bookings",
        json={"vehicleType": "Tata Ace", "distanceKm": 10, "pickup": "A", "drop": "B", "date": "2026-09-20", "lotId": "lot-1"},
        headers=_auth_header(farmer),
    )
    assert resp.status_code == 200
    booking_id = resp.json()["id"]
    assert resp.json()["lotId"] == "lot-1"

    resp = await client.get("/v1/transport/bookings", headers=_auth_header(transporter))
    booking = next(b for b in resp.json()["data"] if b["id"] == booking_id)
    assert booking["lot"]["crop"] == "Tomato"
    assert booking["lot"]["quantityQuintals"] == 10


async def test_booking_with_other_farmers_lot_404(client, fake_firebase, fake_users, fake_db):
    farmer = await _login(client, fake_users)
    fake_db["market_lots"]["lot-2"] = {"id": "lot-2", "farmerId": "uid-2", "crop": "Onion", "quantityQuintals": 5, "expectedRate": 1800, "status": "open"}

    resp = await client.post(
        "/v1/transport/bookings",
        json={"vehicleType": "Tata Ace", "distanceKm": 10, "pickup": "A", "drop": "B", "date": "2026-09-20", "lotId": "lot-2"},
        headers=_auth_header(farmer),
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "LOT_NOT_FOUND"


async def test_booking_with_sold_lot_409(client, fake_firebase, fake_users, fake_db):
    farmer = await _login(client, fake_users)
    fake_db["market_lots"]["lot-3"] = {"id": "lot-3", "farmerId": "uid-1", "crop": "Onion", "quantityQuintals": 5, "expectedRate": 1800, "status": "sold"}

    resp = await client.post(
        "/v1/transport/bookings",
        json={"vehicleType": "Tata Ace", "distanceKm": 10, "pickup": "A", "drop": "B", "date": "2026-09-20", "lotId": "lot-3"},
        headers=_auth_header(farmer),
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "LOT_NOT_OPEN"
