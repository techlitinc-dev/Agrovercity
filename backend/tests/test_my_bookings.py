def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    fake_users["users"]["uid-1"]["activeProfile"] = "farmer"
    fake_users["users"]["uid-1"]["id"] = "uid-1"
    return resp.json()["accessToken"]


def _seed_equipment_booking(fake_db, booking_id="eq-1", status="booked", date="2026-09-20"):
    fake_db["users/uid-1/equipment_bookings"][booking_id] = {
        "id": booking_id,
        "equipmentId": "eq-1",
        "slotId": "eq-1_2026-09-20_0",
        "date": date,
        "slotName": "6:00 AM – 10:00 AM",
        "priceRupees": 800,
        "status": status,
    }


def _seed_transport_booking(fake_db, booking_id="tr-1", status="requested", date="2026-09-21", fare=850):
    fake_db["transport_bookings"][booking_id] = {
        "id": booking_id,
        "userId": "uid-1",
        "vehicleType": "Tata Ace",
        "pickup": "Ozarkhed",
        "drop": "Nashik APMC",
        "date": date,
        "fare": fare,
        "status": status,
    }


async def test_aggregate_three_sources(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    _seed_equipment_booking(fake_db)
    _seed_transport_booking(fake_db)

    resp = await client.get("/v1/users/me/bookings", headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["equipment"]) == 1
    assert body["equipment"][0]["kind"] == "equipment"
    assert body["vet"] == []
    assert len(body["transport"]) == 1
    assert body["transport"][0]["fare"] == 850


async def test_missing_vet_subcollection_returns_empty_list(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.get("/v1/users/me/bookings", headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json()["vet"] == []


async def test_status_filter(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    _seed_equipment_booking(fake_db, status="booked")
    _seed_transport_booking(fake_db, status="requested")

    resp = await client.get("/v1/users/me/bookings", params={"status": "requested"}, headers=_auth_header(access))
    body = resp.json()
    assert body["equipment"] == []
    assert len(body["transport"]) == 1


async def test_sorted_by_date_desc(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    _seed_transport_booking(fake_db, booking_id="tr-1", date="2026-09-21")
    _seed_transport_booking(fake_db, booking_id="tr-2", date="2026-09-25")

    resp = await client.get("/v1/users/me/bookings", headers=_auth_header(access))
    dates = [b["date"] for b in resp.json()["transport"]]
    assert dates == sorted(dates, reverse=True)


async def test_unauthenticated_401(client, fake_firebase, fake_users, fake_db):
    resp = await client.get("/v1/users/me/bookings")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "MISSING_TOKEN"


async def test_kind_field_on_every_item(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    _seed_equipment_booking(fake_db)
    _seed_transport_booking(fake_db)
    fake_db["users/uid-1/vet_bookings"]["vet-1"] = {"id": "vet-1", "vetName": "Dr. Patil", "status": "confirmed", "date": "2026-09-22"}

    resp = await client.get("/v1/users/me/bookings", headers=_auth_header(access))
    body = resp.json()
    assert all(b["kind"] == "equipment" for b in body["equipment"])
    assert all(b["kind"] == "vet" for b in body["vet"])
    assert all(b["kind"] == "transport" for b in body["transport"])


async def test_transport_source_uses_fare_field(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    _seed_transport_booking(fake_db, fare=1200)

    resp = await client.get("/v1/users/me/bookings", headers=_auth_header(access))
    transport = resp.json()["transport"][0]
    assert transport["fare"] == 1200
    assert "totalFare" not in transport
