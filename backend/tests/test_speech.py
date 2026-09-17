def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    fake_users["users"]["uid-1"]["id"] = "uid-1"
    return resp.json()["accessToken"]


async def test_stt_canned_dev_mode(client, fake_firebase, fake_users):
    access = await _login(client, fake_users)
    resp = await client.post(
        "/v1/speech/stt",
        files={"file": ("voice.m4a", b"\x00" * 1000, "audio/mp4")},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["text"]
    assert body["language"] == "hi"


async def test_stt_bad_type_415(client, fake_firebase, fake_users):
    access = await _login(client, fake_users)
    resp = await client.post(
        "/v1/speech/stt",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        headers=_auth_header(access),
    )
    assert resp.status_code == 415


async def test_stt_oversize_413(client, fake_firebase, fake_users):
    access = await _login(client, fake_users)
    resp = await client.post(
        "/v1/speech/stt",
        files={"file": ("voice.m4a", b"\x00" * (6 * 1024 * 1024), "audio/mp4")},
        headers=_auth_header(access),
    )
    assert resp.status_code == 413


async def test_tts_stub_returns_url(client, fake_firebase, fake_users):
    access = await _login(client, fake_users)
    resp = await client.post("/v1/speech/tts", json={"text": "नमस्ते", "language": "hi"}, headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json()["audioUrl"].startswith("http")


async def test_tts_empty_text_422(client, fake_firebase, fake_users):
    access = await _login(client, fake_users)
    resp = await client.post("/v1/speech/tts", json={"text": ""}, headers=_auth_header(access))
    assert resp.status_code == 422
