import pytest

from app.core.cache import cache_delete


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users, fake_db) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    fake_users["users"]["uid-1"]["activeProfile"] = "farmer"
    fake_users["users"]["uid-1"]["id"] = "uid-1"
    fake_db["users"]["uid-1"] = {"id": "uid-1", "agriCoins": 0}
    return resp.json()["accessToken"]


async def _set_mpin(client, access):
    resp = await client.post("/v1/auth/mpin/set", json={"mpin": "1234"}, headers=_auth_header(access))
    assert resp.status_code == 200


async def test_delete_wrong_mpin_401(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db)
    await _set_mpin(client, access)
    await cache_delete("del_attempts:uid-1")

    resp = await client.request("DELETE", "/v1/users/me", json={"mpin": "9999"}, headers=_auth_header(access))
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "WRONG_MPIN"


async def test_delete_purges_everything(client, fake_firebase, fake_users, fake_db, monkeypatch):
    from firebase_admin import auth as fb_auth

    delete_user_calls = []
    monkeypatch.setattr(fb_auth, "delete_user", lambda uid: delete_user_calls.append(uid))

    access = await _login(client, fake_users, fake_db)
    await _set_mpin(client, access)
    await cache_delete("del_attempts:uid-1")
    fake_db["users/uid-1/diary_entries"]["d1"] = {"id": "d1", "title": "x"}
    fake_db["users/uid-1/devices"]["dev1"] = {"id": "dev1"}

    resp = await client.request("DELETE", "/v1/users/me", json={"mpin": "1234"}, headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["deleted"] is True
    assert body["purged"]["authDeleted"] is True
    assert delete_user_calls == ["uid-1"]
    assert "uid-1" not in fake_db["users"]
    assert fake_db["users/uid-1/diary_entries"] == {}
    assert fake_db["users/uid-1/devices"] == {}


async def test_delete_rate_limited_429(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db)
    await _set_mpin(client, access)
    await cache_delete("del_attempts:uid-1")

    statuses = []
    for _ in range(4):
        resp = await client.request("DELETE", "/v1/users/me", json={"mpin": "9999"}, headers=_auth_header(access))
        statuses.append(resp.status_code)
    assert statuses[:3] == [401, 401, 401]
    assert statuses[3] == 429
    assert resp.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"


async def test_register_device_idempotent(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db)
    body = {"fcmToken": "tok-abc", "platform": "android", "locale": "hi"}

    resp1 = await client.post("/v1/devices", json=body, headers=_auth_header(access))
    resp2 = await client.post("/v1/devices", json=body, headers=_auth_header(access))
    assert resp1.status_code == 201
    assert resp2.status_code == 201
    assert resp1.json() == {"registered": True}

    devices = fake_db["users/uid-1/devices"]
    assert len(devices) == 1
    _ = pytest
