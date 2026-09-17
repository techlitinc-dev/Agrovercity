from app.core import db
from app.services.blocks import blocked_pair, list_blocked_ids


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users, uid="uid-1", name="Ramesh") -> str:
    if uid == "uid-1":
        resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
        assert resp.status_code == 200
        fake_users["users"]["uid-1"]["id"] = "uid-1"
        fake_users["users"]["uid-1"]["name"] = name
        return resp.json()["accessToken"]
    fake_users["users"][uid] = {"id": uid, "activeProfile": "farmer", "linkedProfiles": ["farmer"], "referralCode": f"ref_{uid[:8]}", "name": name}
    from app.services.tokens import create_access_token

    return create_access_token(uid)


async def test_report_201(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    other = await _login(client, fake_users, uid="uid-2", name="Suresh")
    _ = other

    resp = await client.post("/v1/users/uid-2/report", json={"reason": "भाव में धोखाधड़ी की कोशिश"}, headers=_auth_header(access))
    assert resp.status_code == 201
    assert resp.json()["reported"] is True

    resp = await client.post("/v1/users/uid-2/report", json={"reason": "दोबारा रिपोर्ट"}, headers=_auth_header(access))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ALREADY_REPORTED"

    resp = await client.post("/v1/users/uid-1/report", json={"reason": "खुद को रिपोर्ट"}, headers=_auth_header(access))
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "CANNOT_REPORT_SELF"


async def test_block_unblock(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    await _login(client, fake_users, uid="uid-2", name="Suresh")

    resp = await client.post("/v1/users/me/blocks", json={"userId": "uid-2"}, headers=_auth_header(access))
    assert resp.status_code == 201
    assert resp.json()["blocked"] is True

    resp = await client.get("/v1/users/me/blocks", headers=_auth_header(access))
    assert resp.json()["total"] == 1

    resp = await client.delete("/v1/users/me/blocks/uid-2", headers=_auth_header(access))
    assert resp.status_code == 204

    resp = await client.get("/v1/users/me/blocks", headers=_auth_header(access))
    assert resp.json()["total"] == 0


async def test_blocked_pair_bidirectional(client, fake_firebase, fake_users, fake_db):
    await _login(client, fake_users)
    await _login(client, fake_users, uid="uid-2", name="Suresh")
    await db.set_subdoc_at("users/uid-1/blocks", "uid-2", {"id": "uid-2", "at": "2026-09-17T00:00:00Z"})

    assert await blocked_pair("uid-1", "uid-2") is True
    assert await blocked_pair("uid-2", "uid-1") is True


async def test_channel_chat_filters_blocked(client, fake_firebase, fake_users, fake_db):
    from app.data.content_seed import seed_content

    await seed_content()
    access_a = await _login(client, fake_users)
    access_b = await _login(client, fake_users, uid="uid-2", name="Suresh")
    _ = access_b

    fake_db["channels/ch-1/chat"]["m1"] = {"id": "m1", "userId": "uid-1", "userName": "Ramesh", "text": "from A", "sentAt": "2026-09-17T00:00:00Z"}
    fake_db["channels/ch-1/chat"]["m2"] = {"id": "m2", "userId": "uid-2", "userName": "Suresh", "text": "from B", "sentAt": "2026-09-17T01:00:00Z"}

    # A blocks B
    await db.set_subdoc_at("users/uid-1/blocks", "uid-2", {"id": "uid-2", "at": "2026-09-17T02:00:00Z"})

    resp = await client.get("/v1/channels/ch-1/chat", headers=_auth_header(access_a))
    texts = [m["text"] for m in resp.json()["data"]]
    assert "from B" not in texts
    assert "from A" in texts
