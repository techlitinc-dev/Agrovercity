from datetime import timedelta

from scripts.seed_equipment import EQUIPMENT

from app.services.equipment import today_ist


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _seed_equipment(fake_db, verified=False):
    for doc in EQUIPMENT:
        doc = {**doc, "docStatus": "verified" if verified else "pending"}
        fake_db["equipment"][doc["id"]] = doc


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


async def test_owner_create_update_machine(client, fake_firebase, fake_users, fake_db):
    owner = await _login(client, fake_users, uid="uid-2", profile="equipmentRental")
    resp = await client.post(
        "/v1/equipment",
        json={"name": "New Tractor", "type": "tractor", "hourlyRate": 700},
        headers=_auth_header(owner),
    )
    assert resp.status_code == 200
    equipment_id = resp.json()["id"]
    assert resp.json()["ownerType"] == "private"
    assert resp.json()["docStatus"] == "pending"

    fake_db["equipment"][equipment_id]["docStatus"] = "verified"

    custom = [
        {"slotName": "5:00 AM – 9:00 AM", "duration": "4 hours", "priceRupees": 900, "recommendedTask": "Custom task 1"},
        {"slotName": "9:00 AM – 1:00 PM", "duration": "4 hours", "priceRupees": 950, "recommendedTask": "Custom task 2"},
    ]
    resp = await client.put(
        f"/v1/equipment/{equipment_id}",
        json={"name": "New Tractor", "type": "tractor", "hourlyRate": 700, "slotTemplate": custom},
        headers=_auth_header(owner),
    )
    assert resp.status_code == 200

    next_day = (today_ist() + timedelta(days=1)).isoformat()
    resp = await client.get(f"/v1/equipment/{equipment_id}/slots", params={"date": next_day}, headers=_auth_header(owner))
    assert resp.status_code == 200
    slot_names = [s["slotName"] for s in resp.json()["data"]]
    assert slot_names == ["5:00 AM – 9:00 AM", "9:00 AM – 1:00 PM"]


async def test_owner_forbidden_for_farmer(client, fake_firebase, fake_users, fake_db):
    farmer = await _login(client, fake_users)
    resp = await client.post(
        "/v1/equipment",
        json={"name": "X", "type": "tractor", "hourlyRate": 100},
        headers=_auth_header(farmer),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN_ROLE"


async def test_fleet_summary(client, fake_firebase, fake_users, fake_db):
    _seed_equipment(fake_db, verified=True)
    owner = await _login(client, fake_users, uid="uid-2", profile="equipmentRental")
    farmer = await _login(client, fake_users)
    fake_db["equipment"]["eq-2"]["ownerId"] = "uid-2"

    slots = (await client.get("/v1/equipment/eq-2/slots", headers=_auth_header(farmer))).json()["data"]
    resp = await client.post(f"/v1/equipment/slots/{slots[0]['id']}/book", json={"farmerName": "Ramesh"}, headers=_auth_header(farmer))
    assert resp.status_code == 200

    resp = await client.get("/v1/equipment/owner/fleet", headers=_auth_header(owner))
    assert resp.status_code == 200
    rows = resp.json()["data"]
    row = next(r for r in rows if r["equipmentId"] == "eq-2")
    assert row["bookedHoursThisWeek"] == 4
    assert row["weeklyIncome"] == 800
    assert row["docStatus"] == "verified"


async def test_new_machine_pending_hidden_from_farmers(client, fake_firebase, fake_users, fake_db):
    owner = await _login(client, fake_users, uid="uid-2", profile="equipmentRental")
    farmer = await _login(client, fake_users)

    resp = await client.post(
        "/v1/equipment",
        json={"name": "Hidden Machine", "type": "tractor", "hourlyRate": 700},
        headers=_auth_header(owner),
    )
    equipment_id = resp.json()["id"]

    resp = await client.get("/v1/equipment", headers=_auth_header(farmer))
    assert all(d["id"] != equipment_id for d in resp.json()["data"])

    resp = await client.get(f"/v1/equipment/{equipment_id}/slots", headers=_auth_header(farmer))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "EQUIPMENT_NOT_FOUND"


async def test_verified_machine_visible(client, fake_firebase, fake_users, fake_db):
    _seed_equipment(fake_db, verified=True)
    farmer = await _login(client, fake_users)
    resp = await client.get("/v1/equipment", headers=_auth_header(farmer))
    ids = [d["id"] for d in resp.json()["data"]]
    assert "eq-1" in ids and "eq-2" in ids

    resp = await client.get("/v1/equipment/eq-1/slots", headers=_auth_header(farmer))
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 4


async def test_fleet_includes_doc_status(client, fake_firebase, fake_users, fake_db):
    _seed_equipment(fake_db, verified=True)
    fake_db["equipment"]["eq-2"]["ownerId"] = "uid-2"
    owner = await _login(client, fake_users, uid="uid-2", profile="equipmentRental")

    resp = await client.get("/v1/equipment/owner/fleet", headers=_auth_header(owner))
    rows = resp.json()["data"]
    assert all("docStatus" in r for r in rows)
