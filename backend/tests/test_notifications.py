import firebase_admin
import pytest
from firebase_admin import messaging

from app.services import claims as claims_service
from app.services import fcm as fcm_service


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users, fake_db) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    fake_users["users"]["uid-1"]["id"] = "uid-1"
    return resp.json()["accessToken"]


async def test_mark_read(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db)
    fake_db["users/uid-1/notifications"]["n1"] = {"id": "n1", "title": "a", "read": False, "createdAt": "2026-09-17T00:00:00Z"}
    fake_db["users/uid-1/notifications"]["n2"] = {"id": "n2", "title": "b", "read": False, "createdAt": "2026-09-17T01:00:00Z"}

    resp = await client.post("/v1/notifications/read", json={"notificationIds": ["n1", "n2"]}, headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json()["markedRead"] == 2

    resp = await client.get("/v1/notifications", headers=_auth_header(access))
    assert all(d["read"] for d in resp.json()["data"])


async def test_mark_all_with_empty_list(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db)
    fake_db["users/uid-1/notifications"]["n1"] = {"id": "n1", "title": "a", "read": False, "createdAt": "2026-09-17T00:00:00Z"}

    resp = await client.post("/v1/notifications/read", json={"notificationIds": []}, headers=_auth_header(access))
    assert resp.json()["markedRead"] == 1


async def test_advance_status_notifies(client, fake_firebase, fake_users, fake_db, monkeypatch):
    calls = []

    async def fake_notify(uid, title, body, data):
        calls.append((uid, title, body, data))

    monkeypatch.setattr(fcm_service, "notify", fake_notify)
    claim = {
        "id": "claim-1",
        "claimNumber": "CLM-2026-MH-0001",
        "status": "intimated",
        "statusText": "",
        "timeline": [],
    }
    await claims_service.advance_status(claim, "surveyorAssigned", uid="uid-1")
    assert len(calls) == 1
    assert "CLM-2026-MH-0001" in calls[0][1]
    assert calls[0][3]["type"] == "claim"


async def test_unregistered_token_pruned(client, fake_firebase, fake_users, fake_db, monkeypatch):
    fake_db["users/uid-1/devices"]["tokhash1"] = {"id": "tokhash1", "fcmToken": "dead-token"}
    fake_db["users/uid-1/devices"]["tokhash2"] = {"id": "tokhash2", "fcmToken": "live-token"}

    monkeypatch.setattr(firebase_admin, "_apps", {"default": object()})

    class FakeResp:
        def __init__(self, success, exception=None):
            self.success = success
            self.exception = exception

    class FakeMulticastResponse:
        responses = [
            FakeResp(False, messaging.UnregisteredError("unregistered")),
            FakeResp(True),
        ]

    sent = []
    monkeypatch.setattr(
        messaging,
        "send_each_for_multicast",
        lambda message: sent.append(message) or FakeMulticastResponse(),
    )

    sent_count = await fcm_service.send_to_user("uid-1", "t", "b", {"type": "test"})
    assert sent_count == 1
    assert "tokhash1" not in fake_db["users/uid-1/devices"]
    assert "tokhash2" in fake_db["users/uid-1/devices"]
    assert sent[0].tokens == ["dead-token", "live-token"]


async def test_notify_writes_firestore_doc(client, fake_firebase, fake_users, fake_db):
    await _login(client, fake_users, fake_db)
    doc_id = await fcm_service.notify("uid-1", "शीर्षक", "संदेश", {"type": "claim"})
    doc = fake_db["users/uid-1/notifications"][doc_id]
    assert doc["read"] is False
    assert doc["title"] == "शीर्षक"
