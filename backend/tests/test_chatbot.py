import uuid

from app.services import llm as llm_service
from app.services.llm import LLMUnavailable


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    fake_users["users"]["uid-1"]["id"] = "uid-1"
    fake_users["users"]["uid-1"]["name"] = "Ramesh"
    return resp.json()["accessToken"]


async def test_send_message_bot_reply(client, fake_firebase, fake_users, fake_db, monkeypatch):
    async def fake_complete(messages):
        return "नमस्ते! आपका सवाल दर्ज है।"

    monkeypatch.setattr(llm_service, "complete", fake_complete)
    session_id = uuid.uuid4().hex
    access = await _login(client, fake_users)

    resp = await client.post(
        "/v1/chatbot/messages",
        json={"text": "नमस्ते", "language": "hi", "sessionId": session_id},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sender"] == "bot"
    assert "नमस्ते" in body["text"]
    assert len(fake_db[f"chat_sessions/{session_id}/messages"]) == 2


async def test_context_retained_across_turns(client, fake_firebase, fake_users, fake_db, monkeypatch):
    calls = []

    async def fake_complete(messages):
        calls.append(list(messages))
        return "उत्तर"

    monkeypatch.setattr(llm_service, "complete", fake_complete)
    session_id = uuid.uuid4().hex
    access = await _login(client, fake_users)

    await client.post("/v1/chatbot/messages", json={"text": "पहला सवाल", "sessionId": session_id}, headers=_auth_header(access))
    await client.post("/v1/chatbot/messages", json={"text": "दूसरा सवाल", "sessionId": session_id}, headers=_auth_header(access))
    assert len(calls) == 2
    assert len(calls[1]) >= 3  # system + user + bot from turn 1


async def test_mandi_keyword_rich_card(client, fake_firebase, fake_users, fake_db, monkeypatch):
    async def fake_complete(messages):
        return "मंडी भाव देखें।"

    monkeypatch.setattr(llm_service, "complete", fake_complete)
    session_id = uuid.uuid4().hex
    access = await _login(client, fake_users)

    resp = await client.post(
        "/v1/chatbot/messages",
        json={"text": "आज प्याज का भाव क्या है?", "sessionId": session_id},
        headers=_auth_header(access),
    )
    body = resp.json()
    assert body["richCardType"] == "mandi"
    assert body["quickReplies"]


async def test_empty_message_400(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.post(
        "/v1/chatbot/messages",
        json={"language": "hi", "sessionId": uuid.uuid4().hex},
        headers=_auth_header(access),
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "EMPTY_MESSAGE"


async def test_llm_outage_graceful(client, fake_firebase, fake_users, fake_db, monkeypatch):
    async def failing_complete(messages):
        raise LLMUnavailable("down")

    monkeypatch.setattr(llm_service, "complete", failing_complete)
    session_id = uuid.uuid4().hex
    access = await _login(client, fake_users)

    resp = await client.post(
        "/v1/chatbot/messages",
        json={"text": "मौसम?", "sessionId": session_id},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["text"] == "अभी सेवा उपलब्ध नहीं है — थोड़ी देर बाद पूछें"
    assert body["richCardType"] is None


async def test_handoff_returns_expert(client, fake_firebase, fake_users, fake_db, monkeypatch):
    async def fake_complete(messages):
        return "उत्तर"

    monkeypatch.setattr(llm_service, "complete", fake_complete)
    session_id = uuid.uuid4().hex
    access = await _login(client, fake_users)
    await client.post("/v1/chatbot/messages", json={"text": "मदद चाहिए", "sessionId": session_id}, headers=_auth_header(access))

    resp = await client.post(
        "/v1/chatbot/handoff",
        json={"sessionId": session_id, "reason": "जटिल समस्या"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["etaMinutes"] == 30
    assert body["threadId"]
    handoffs = list(fake_db["handoff_requests"].values())
    assert len(handoffs[0]["lastMessages"]) == 2


async def test_history_pagination(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    sid = "sess-hist"
    for i in range(7):
        fake_db[f"chat_sessions/{sid}/messages"][f"m{i}"] = {
            "sender": "user" if i % 2 == 0 else "bot",
            "text": f"msg {i}",
            "timestamp": f"2026-09-17T00:00:0{i}Z",
        }

    resp = await client.get(
        "/v1/chatbot/history",
        params={"sessionId": sid, "page": 2, "pageSize": 3},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 7
    assert body["page"] == 2
    assert body["pageSize"] == 3
    assert len(body["data"]) == 3
    assert body["data"][0]["text"] == "msg 3"


async def test_history_empty_session(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.get(
        "/v1/chatbot/history",
        params={"sessionId": "sess-empty"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []
    assert body["total"] == 0


async def test_history_missing_session_id_422(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.get("/v1/chatbot/history", headers=_auth_header(access))
    assert resp.status_code == 422
