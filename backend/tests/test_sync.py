from datetime import timedelta

from app.services.equipment import today_ist


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _diary_op(key: str, **body_overrides) -> dict:
    return {
        "idempotencyKey": key,
        "method": "POST",
        "path": "/v1/diary/entries",
        "body": {"title": "Urea", "category": "fertilizer", "type": "expense", "amount": 450, "date": "2026-09-13", **body_overrides},
        "queuedAt": "2026-09-13T00:00:00Z",
    }


async def _login(client, fake_users, fake_db) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    fake_users["users"]["uid-1"]["activeProfile"] = "farmer"
    fake_users["users"]["uid-1"]["id"] = "uid-1"
    fake_db["users"]["uid-1"] = {"id": "uid-1", "agriCoins": 0}
    return resp.json()["accessToken"]


async def test_replay_two_diary_ops(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db)
    batch = {"operations": [_diary_op("k1"), _diary_op("k2")]}
    resp = await client.post("/v1/sync", json=batch, headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["applied"] == 2
    assert body["errors"] == 0
    assert len(fake_db["users/uid-1/diary_entries"]) == 2


async def test_replay_is_idempotent(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db)
    batch = {"operations": [_diary_op("k1")]}
    await client.post("/v1/sync", json=batch, headers=_auth_header(access))
    resp = await client.post("/v1/sync", json=batch, headers=_auth_header(access))
    body = resp.json()
    assert all(r["status"] == "duplicate" for r in body["results"])
    assert len(fake_db["users/uid-1/diary_entries"]) == 1


async def test_unknown_path_per_op_error(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db)
    batch = {
        "operations": [
            _diary_op("k1"),
            {"idempotencyKey": "k9", "method": "POST", "path": "/v1/whatever", "body": {}, "queuedAt": "x"},
        ]
    }
    resp = await client.post("/v1/sync", json=batch, headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["applied"] == 1
    assert body["errors"] == 1
    assert body["results"][1]["error"]["code"] == "UNSUPPORTED_PATH"


async def test_over_50_ops_422(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db)
    ops = [_diary_op(f"k{i}") for i in range(51)]
    resp = await client.post("/v1/sync", json={"operations": ops}, headers=_auth_header(access))
    assert resp.status_code == 422


async def test_conflicting_booking_op_409_in_batch(client, fake_firebase, fake_users, fake_db, monkeypatch):
    from app.services import storage as storage_service

    monkeypatch.setattr(
        storage_service,
        "upload_user_file",
        lambda uid, data, filename, content_type, prefix="claims": (f"{prefix}/{uid}/f", len(data)),
    )
    tomorrow = (today_ist() + timedelta(days=1)).isoformat()
    future = (today_ist() + timedelta(days=3)).isoformat()
    fake_db["equipment_slots"]["slot-x"] = {
        "id": "slot-x", "equipmentId": "eq-1", "date": tomorrow,
        "slotName": "6:00 AM – 10:00 AM", "status": "available", "bookedByName": None,
        "priceRupees": 800,
    }
    fake_db["equipment"]["eq-1"] = {"id": "eq-1", "ownerType": "fpo", "name": "Tractor"}
    fake_db["equipment_slots"]["slot-y"] = {
        "id": "slot-y", "equipmentId": "eq-1", "date": future,
        "slotName": "6:00 AM – 10:00 AM", "status": "available", "bookedByName": None,
    }
    # two existing bookings on tomorrow's date -> third violates max-2
    fake_db["equipment_bookings"]["b1"] = {"id": "b1", "userId": "uid-1", "date": tomorrow, "status": "booked"}
    fake_db["equipment_bookings"]["b2"] = {"id": "b2", "userId": "uid-1", "date": tomorrow, "status": "booked"}

    access = await _login(client, fake_users, fake_db)
    batch = {
        "operations": [
            {"idempotencyKey": "kb1", "method": "POST", "path": "/v1/equipment/slots/slot-x/book", "body": {"farmerName": "Ramesh"}, "queuedAt": "x"},
            _diary_op("kd1"),
        ]
    }
    resp = await client.post("/v1/sync", json=batch, headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"][0]["status"] == "error"
    assert body["results"][0]["httpStatus"] == 409
    assert body["results"][0]["error"]["code"] == "MAX_SLOTS_PER_DAY"
    assert body["results"][1]["status"] == "applied"


async def test_replay_strips_server_owned_fields(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db)
    batch = {"operations": [_diary_op("k-strip", agriCoinsEarned=9999, status="hacked")]}
    resp = await client.post("/v1/sync", json=batch, headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json()["results"][0]["status"] == "applied"
    entry = next(iter(fake_db["users/uid-1/diary_entries"].values()))
    assert "agriCoinsEarned" not in entry
    assert "status" not in entry
    assert fake_db["users"]["uid-1"]["agriCoins"] == 15


async def test_claim_replay_ignores_status_field(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db)
    fake_users["users"]["uid-1"]["state"] = "Maharashtra"
    fake_users["users"]["uid-1"]["district"] = "Nashik"
    fake_db["users/uid-1/insurance_policies"]["pol-1"] = {"id": "pol-1", "sumInsured": 80000}
    batch = {
        "operations": [
            {
                "idempotencyKey": "kc1",
                "method": "POST",
                "path": "/v1/insurance/claims",
                "body": {
                    "policyId": "pol-1", "cropName": "Wheat", "calamityType": "hailstorm",
                    "dateOfDamage": "2026-09-10", "cropStage": "flowering",
                    "estimatedLossPercent": 40, "gpsCoordinates": "20.0,73.8", "village": "Ozarkhed",
                    "damagePhotos": ["https://storage/p1.jpg"], "status": "disbursed",
                },
                "queuedAt": "x",
            }
        ]
    }
    resp = await client.post("/v1/sync", json=batch, headers=_auth_header(access))
    assert resp.status_code == 200
    claim = next(iter(fake_db["users/uid-1/insurance_claims"].values()))
    assert claim["status"] == "intimated"
