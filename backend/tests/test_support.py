def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users, uid="uid-1", name="Ramesh") -> str:
    if uid == "uid-1":
        resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
        assert resp.status_code == 200
        fake_users["users"]["uid-1"]["id"] = "uid-1"
        fake_users["users"]["uid-1"]["name"] = name
        return resp.json()["accessToken"]
    fake_users["users"][uid] = {"id": uid, "activeProfile": "farmer", "linkedProfiles": ["farmer"], "referralCode": f"ref_{uid[:8]}"}
    from app.services.tokens import create_access_token

    return create_access_token(uid)


async def test_handoff_creates_thread(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.post(
        "/v1/chatbot/handoff",
        json={"sessionId": "s1", "reason": "जटिल समस्या"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    thread_id = resp.json()["threadId"]

    resp = await client.get("/v1/support/threads", headers=_auth_header(access))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["id"] == thread_id
    assert data[0]["status"] == "open"


async def test_post_message_and_list(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    thread_id = (
        await client.post(
            "/v1/chatbot/handoff",
            json={"sessionId": "s1", "reason": "जटिल समस्या"},
            headers=_auth_header(access),
        )
    ).json()["threadId"]

    resp = await client.post(
        f"/v1/support/threads/{thread_id}/messages",
        json={"text": "कृपया मेरी समस्या देखें"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 201
    assert resp.json()["sender"] == "user"

    resp = await client.get(f"/v1/support/threads/{thread_id}/messages", headers=_auth_header(access))
    assert resp.json()["total"] == 1
    assert fake_db["support_threads"][thread_id]["lastMessageAt"]


async def test_foreign_thread_404(client, fake_firebase, fake_users, fake_db):
    access_a = await _login(client, fake_users)
    thread_id = (
        await client.post(
            "/v1/chatbot/handoff",
            json={"sessionId": "s1", "reason": "जटिल समस्या"},
            headers=_auth_header(access_a),
        )
    ).json()["threadId"]

    access_b = await _login(client, fake_users, uid="uid-2", name="Suresh")
    resp = await client.get(f"/v1/support/threads/{thread_id}/messages", headers=_auth_header(access_b))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "THREAD_NOT_FOUND"

    resp = await client.post(
        f"/v1/support/threads/{thread_id}/messages",
        json={"text": "hello"},
        headers=_auth_header(access_b),
    )
    assert resp.status_code == 404


async def test_expert_message_visible(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    thread_id = (
        await client.post(
            "/v1/chatbot/handoff",
            json={"sessionId": "s1", "reason": "जटिल समस्या"},
            headers=_auth_header(access),
        )
    ).json()["threadId"]
    fake_db[f"support_threads/{thread_id}/messages"]["exp1"] = {
        "id": "exp1",
        "sender": "expert",
        "text": "मैं देख रहा हूं",
        "at": "2026-09-17T01:00:00Z",
    }

    resp = await client.get(f"/v1/support/threads/{thread_id}/messages", headers=_auth_header(access))
    senders = [m["sender"] for m in resp.json()["data"]]
    assert "expert" in senders
