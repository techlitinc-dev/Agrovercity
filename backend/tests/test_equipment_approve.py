from app.services.tokens import create_access_token


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users, uid="uid-1", profile="farmer") -> str:
    if uid == "uid-1":
        resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
        assert resp.status_code == 200
        fake_users["users"]["uid-1"]["activeProfile"] = profile
        fake_users["users"]["uid-1"]["id"] = "uid-1"
        fake_users["users"]["uid-1"]["name"] = "Ramesh"
        return resp.json()["accessToken"]
    fake_users["users"][uid] = {"id": uid, "activeProfile": profile, "linkedProfiles": [profile], "referralCode": f"ref_{uid[:8]}", "name": f"Farmer {uid}"}
    return create_access_token(uid)


async def _setup_pending_booking(client, fake_users, fake_db, owner_uid="uid-2") -> str:
    """Owner machine + farmer booking (pending). Returns booking_id."""
    owner = await _login(client, fake_users, uid=owner_uid, profile="equipmentRental")
    resp = await client.post(
        "/v1/equipment",
        json={"name": f"Machine {owner_uid}", "type": "tractor", "hourlyRate": 700},
        headers=_auth_header(owner),
    )
    equipment_id = resp.json()["id"]
    fake_db["equipment"][equipment_id]["docStatus"] = "verified"

    farmer = await _login(client, fake_users)
    slots = (await client.get(f"/v1/equipment/{equipment_id}/slots", headers=_auth_header(farmer))).json()["data"]
    resp = await client.post(f"/v1/equipment/slots/{slots[0]['id']}/book", json={"farmerName": "Ramesh"}, headers=_auth_header(farmer))
    assert resp.json()["status"] == "pending"
    return resp.json()["booking"]["id"]


async def test_approve_pending_booking(client, fake_firebase, fake_users, fake_db):
    booking_id = await _setup_pending_booking(client, fake_users, fake_db)
    owner = await _login(client, fake_users, uid="uid-2", profile="equipmentRental")

    resp = await client.post(f"/v1/equipment/bookings/{booking_id}/approve", headers=_auth_header(owner))
    assert resp.status_code == 200
    assert resp.json()["status"] == "booked"

    assert fake_db["equipment_bookings"][booking_id]["status"] == "booked"
    notifications = [d for d in fake_db["notifications"].values() if d["userId"] == "uid-1"]
    assert any(n["data"]["type"] == "booking_accepted" for n in notifications)


async def test_approve_non_pending_409(client, fake_firebase, fake_users, fake_db):
    booking_id = await _setup_pending_booking(client, fake_users, fake_db)
    owner = await _login(client, fake_users, uid="uid-2", profile="equipmentRental")
    await client.post(f"/v1/equipment/bookings/{booking_id}/approve", headers=_auth_header(owner))

    resp = await client.post(f"/v1/equipment/bookings/{booking_id}/approve", headers=_auth_header(owner))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ILLEGAL_TRANSITION"


async def test_reject_frees_slot_with_reason(client, fake_firebase, fake_users, fake_db):
    booking_id = await _setup_pending_booking(client, fake_users, fake_db)
    owner = await _login(client, fake_users, uid="uid-2", profile="equipmentRental")
    booking = fake_db["equipment_bookings"][booking_id]
    slot_id = booking["slotId"]

    resp = await client.post(
        f"/v1/equipment/bookings/{booking_id}/reject",
        json={"reason": "मशीन खराब"},
        headers=_auth_header(owner),
    )
    assert resp.status_code == 200
    assert fake_db["equipment_bookings"][booking_id]["status"] == "rejected"
    assert fake_db["equipment_bookings"][booking_id]["rejectionReason"] == "मशीन खराब"
    assert fake_db["equipment_slots"][slot_id]["status"] == "available"


async def test_reject_promotes_waitlist_head(client, fake_firebase, fake_users, fake_db):
    booking_id = await _setup_pending_booking(client, fake_users, fake_db)
    owner = await _login(client, fake_users, uid="uid-2", profile="equipmentRental")
    farmer = await _login(client, fake_users)
    other = await _login(client, fake_users, uid="uid-3", profile="farmer")
    slot_id = fake_db["equipment_bookings"][booking_id]["slotId"]

    resp = await client.post(f"/v1/equipment/slots/{slot_id}/waitlist", headers=_auth_header(other))
    assert resp.status_code == 200

    resp = await client.post(
        f"/v1/equipment/bookings/{booking_id}/reject",
        json={"reason": "ऑपरेटर उपलब्ध नहीं"},
        headers=_auth_header(owner),
    )
    assert resp.status_code == 200
    assert resp.json()["promotedUserId"] == "uid-3"

    promoted = [b for b in fake_db["equipment_bookings"].values() if b["userId"] == "uid-3"]
    assert len(promoted) == 1
    assert promoted[0]["status"] == "pending"
    assert all(d["userId"] != "uid-3" for d in fake_db["equipment_waitlists"].values())

    rejected_notifications = [d for d in fake_db["notifications"].values() if d["userId"] == "uid-1"]
    promoted_notifications = [d for d in fake_db["notifications"].values() if d["userId"] == "uid-3"]
    assert any(n["data"]["type"] == "booking_rejected" for n in rejected_notifications)
    assert any(n["data"]["type"] == "waitlist_promoted" for n in promoted_notifications)
    _ = farmer


async def test_non_owner_approve_403(client, fake_firebase, fake_users, fake_db):
    booking_id = await _setup_pending_booking(client, fake_users, fake_db)
    other_owner = await _login(client, fake_users, uid="uid-3", profile="equipmentRental")

    resp = await client.post(f"/v1/equipment/bookings/{booking_id}/approve", headers=_auth_header(other_owner))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "NOT_EQUIPMENT_OWNER"


async def test_reject_without_reason_422(client, fake_firebase, fake_users, fake_db):
    booking_id = await _setup_pending_booking(client, fake_users, fake_db)
    owner = await _login(client, fake_users, uid="uid-2", profile="equipmentRental")

    resp = await client.post(
        f"/v1/equipment/bookings/{booking_id}/reject",
        json={"reason": "ab"},
        headers=_auth_header(owner),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_pending_inbox_lists_owner_pending_only(client, fake_firebase, fake_users, fake_db):
    booking_1 = await _setup_pending_booking(client, fake_users, fake_db, owner_uid="uid-2")
    booking_2 = await _setup_pending_booking(client, fake_users, fake_db, owner_uid="uid-3")

    owner2 = await _login(client, fake_users, uid="uid-2", profile="equipmentRental")
    owner3 = await _login(client, fake_users, uid="uid-3", profile="equipmentRental")

    resp = await client.get("/v1/equipment/bookings/pending", headers=_auth_header(owner2))
    ids = [r["bookingId"] for r in resp.json()["data"]]
    assert booking_1 in ids
    assert booking_2 not in ids

    resp = await client.get("/v1/equipment/bookings/pending", headers=_auth_header(owner3))
    ids = [r["bookingId"] for r in resp.json()["data"]]
    assert booking_2 in ids
    assert booking_1 not in ids
