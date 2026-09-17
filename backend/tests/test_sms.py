import logging

from app.services import sms as sms_service


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    fake_users["users"]["uid-1"]["id"] = "uid-1"
    return resp.json()["accessToken"]


async def test_dev_mode_logs_only(caplog):
    sender = sms_service.get_sms_sender()
    assert isinstance(sender, sms_service.LogOnlySender)
    with caplog.at_level(logging.INFO, logger="app.services.sms"):
        result = await sender.send("+919811100001", "equipment_reminder", {"equipment": "Tractor"})
    assert result is True
    assert "SMS(dev) to +919811100001" in caplog.text


async def test_cancel_hook_sends_sms(client, fake_firebase, fake_users, fake_db, monkeypatch):
    from scripts.seed_equipment import EQUIPMENT
    from app.services.equipment import today_ist

    for doc in EQUIPMENT:
        fake_db["equipment"][doc["id"]] = doc
    fake_db["users"]["uid-2"] = {"id": "uid-2", "phone": "+919811300099"}

    sent = []

    class SpySender:
        async def send(self, phone, template_id, params):
            sent.append((phone, template_id, params))
            return True

    monkeypatch.setattr(sms_service, "get_sms_sender", lambda: SpySender())

    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    access = resp.json()["accessToken"]
    fake_users["users"]["uid-1"]["activeProfile"] = "farmer"
    fake_users["users"]["uid-1"]["id"] = "uid-1"

    tomorrow = (today_ist().__class__.fromordinal(today_ist().toordinal() + 1)).isoformat()
    slots = (
        await client.get("/v1/equipment/eq-1/slots", params={"date": tomorrow}, headers=_auth_header(access))
    ).json()["data"]
    booking = (
        await client.post(
            f"/v1/equipment/slots/{slots[0]['id']}/book",
            json={"farmerName": "Ramesh"},
            headers=_auth_header(access),
        )
    ).json()["booking"]
    fake_db["equipment"]["eq-1"]["ownerId"] = "uid-2"

    resp = await client.delete(f"/v1/equipment/bookings/{booking['id']}", headers=_auth_header(access))
    assert resp.status_code == 200
    assert any(phone == "+919811300099" and template_id == "equipment_cancel_owner" for phone, template_id, params in sent)


async def test_reminder_hook_sends_sms(client, fake_firebase, fake_users, fake_db, monkeypatch):
    from datetime import datetime

    from app.services import reminders as reminders_service
    from app.services.equipment import IST, today_ist

    sent = []

    class SpySender:
        async def send(self, phone, template_id, params):
            sent.append((phone, template_id, params))
            return True

    monkeypatch.setattr(sms_service, "get_sms_sender", lambda: SpySender())

    fake_db["equipment"]["eq-1"] = {"id": "eq-1", "name": "Tractor", "ownerId": "uid-2", "docStatus": "verified", "active": True}
    now = datetime.now(IST)
    slot_start = now + __import__("datetime").timedelta(minutes=20)
    slot_name = f"{slot_start:%I:%M %p} – {slot_start + __import__('datetime').timedelta(hours=4):%I:%M %p}"
    fake_db["equipment_bookings"]["bk-1"] = {
        "id": "bk-1",
        "userId": "uid-1",
        "equipmentId": "eq-1",
        "date": today_ist().isoformat(),
        "slotName": slot_name,
        "status": "booked",
    }
    fake_db["users"]["uid-1"] = {"id": "uid-1", "phone": "+919812345678"}

    result = await reminders_service.scan_and_send(now=now)
    assert result == {"reminded": 1}
    assert sent[0][0] == "+919812345678"
    assert sent[0][1] == "equipment_reminder"
