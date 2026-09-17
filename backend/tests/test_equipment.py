from datetime import timedelta

from scripts.seed_equipment import EQUIPMENT

from app.services.equipment import IST, today_ist


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _seed_equipment(fake_db):
    for doc in EQUIPMENT:
        fake_db["equipment"][doc["id"]] = doc


def _tomorrow() -> str:
    return (today_ist() + timedelta(days=1)).isoformat()


async def _login(client, fake_users, uid="uid-1", profile="farmer") -> str:
    if uid == "uid-1":
        resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
        assert resp.status_code == 200
        fake_users["users"]["uid-1"]["activeProfile"] = profile
        fake_users["users"]["uid-1"]["id"] = "uid-1"
        return resp.json()["accessToken"]
    fake_users["users"][uid] = {"id": uid, "activeProfile": profile, "linkedProfiles": [profile], "referralCode": f"ref_{uid[:8]}", "name": "Waitlisted Farmer"}
    from app.services.tokens import create_access_token

    return create_access_token(uid)


async def _get_slot(client, access, equipment_id="eq-1", date_str=None, index=0) -> dict:
    resp = await client.get(f"/v1/equipment/{equipment_id}/slots", params={"date": date_str}, headers=_auth_header(access))
    assert resp.status_code == 200
    return resp.json()["data"][index]


async def test_slots_generated_on_first_read(client, fake_firebase, fake_users, fake_db):
    _seed_equipment(fake_db)
    access = await _login(client, fake_users)
    resp = await client.get("/v1/equipment/eq-1/slots", headers=_auth_header(access))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert [s["slotName"] for s in data] == [
        "6:00 AM – 10:00 AM",
        "10:00 AM – 2:00 PM",
        "2:00 PM – 6:00 PM",
        "6:00 PM – 10:00 PM",
    ]
    assert all(s["status"] == "available" for s in data)
    assert all(s["priceRupees"] == 800 for s in data)


async def test_book_fpo_auto_confirms(client, fake_firebase, fake_users, fake_db):
    _seed_equipment(fake_db)
    access = await _login(client, fake_users)
    fake_db["users"]["uid-1"] = {"id": "uid-1", "agriCoins": 0}
    slot = await _get_slot(client, access, "eq-1")

    resp = await client.post(f"/v1/equipment/slots/{slot['id']}/book", json={"farmerName": "Ramesh"}, headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "booked"
    assert body["booking"]["status"] == "booked"
    assert body["agriCoinsEarned"] == 50
    assert fake_db["users"]["uid-1"]["agriCoins"] == 50
    assert fake_db["equipment_slots"][slot["id"]]["bookedByName"] == "Ramesh"


async def test_book_private_pending(client, fake_firebase, fake_users, fake_db):
    _seed_equipment(fake_db)
    access = await _login(client, fake_users)
    slot = await _get_slot(client, access, "eq-2")

    resp = await client.post(f"/v1/equipment/slots/{slot['id']}/book", json={"farmerName": "Ramesh"}, headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


async def test_max_two_slots_per_day(client, fake_firebase, fake_users, fake_db):
    _seed_equipment(fake_db)
    access = await _login(client, fake_users)
    today = today_ist().isoformat()
    slots = (await client.get("/v1/equipment/eq-1/slots", params={"date": today}, headers=_auth_header(access))).json()["data"]

    for slot in slots[:2]:
        resp = await client.post(f"/v1/equipment/slots/{slot['id']}/book", json={"farmerName": "Ramesh"}, headers=_auth_header(access))
        assert resp.status_code == 200

    resp = await client.post(f"/v1/equipment/slots/{slots[2]['id']}/book", json={"farmerName": "Ramesh"}, headers=_auth_header(access))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "MAX_SLOTS_PER_DAY"
    assert "अधिकतम 2" in resp.json()["error"]["message"]


async def test_double_book_same_slot_409(client, fake_firebase, fake_users, fake_db):
    _seed_equipment(fake_db)
    access = await _login(client, fake_users)
    slot = await _get_slot(client, access, "eq-1")

    resp = await client.post(f"/v1/equipment/slots/{slot['id']}/book", json={"farmerName": "Ramesh"}, headers=_auth_header(access))
    assert resp.status_code == 200
    resp = await client.post(f"/v1/equipment/slots/{slot['id']}/book", json={"farmerName": "Suresh"}, headers=_auth_header(access))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "SLOT_UNAVAILABLE"


async def test_cancel_within_2h_blocked(client, fake_firebase, fake_users, fake_db):
    _seed_equipment(fake_db)
    access = await _login(client, fake_users)
    slot = await _get_slot(client, access, "eq-1")

    resp = await client.post(f"/v1/equipment/slots/{slot['id']}/book", json={"farmerName": "Ramesh"}, headers=_auth_header(access))
    booking_id = resp.json()["booking"]["id"]

    # force the slot start to today at midnight — always inside the 2h window
    fake_db["equipment_slots"][slot["id"]]["slotName"] = "12:00 AM – 4:00 AM"
    fake_db["equipment_bookings"][booking_id]["slotName"] = "12:00 AM – 4:00 AM"

    resp = await client.delete(f"/v1/equipment/bookings/{booking_id}", headers=_auth_header(access))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CANCEL_WINDOW_CLOSED"


async def test_cancel_promotes_waitlist(client, fake_firebase, fake_users, fake_db):
    _seed_equipment(fake_db)
    farmer = await _login(client, fake_users)
    other = await _login(client, fake_users, uid="uid-2", profile="farmer")
    tomorrow = _tomorrow()
    slot = await _get_slot(client, farmer, "eq-1", date_str=tomorrow)

    resp = await client.post(f"/v1/equipment/slots/{slot['id']}/book", json={"farmerName": "Ramesh"}, headers=_auth_header(farmer))
    booking_id = resp.json()["booking"]["id"]

    resp = await client.post(f"/v1/equipment/slots/{slot['id']}/waitlist", headers=_auth_header(other))
    assert resp.status_code == 200

    resp = await client.delete(f"/v1/equipment/bookings/{booking_id}", headers=_auth_header(farmer))
    assert resp.status_code == 200
    assert resp.json()["promotedUserId"] == "uid-2"

    assert fake_db["equipment_slots"][slot["id"]]["status"] == "booked"
    assert "equipment_waitlists" not in fake_db or all(
        d["userId"] != "uid-2" for d in fake_db.get("equipment_waitlists", {}).values()
    )
    promoted = [b for b in fake_db["equipment_bookings"].values() if b["userId"] == "uid-2"]
    assert len(promoted) == 1
    assert promoted[0]["status"] == "booked"
