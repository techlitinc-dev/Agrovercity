PNG_1KB = b"\x89PNG\r\n\x1a\n" + b"x" * 1008


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    fake_users["users"]["uid-1"]["id"] = "uid-1"
    return resp.json()["accessToken"]


async def test_upload_png_201(client, fake_firebase, fake_users, fake_db, monkeypatch):
    from app.services import storage as storage_service

    def fake_upload(uid, data, filename, content_type, prefix="vault"):
        return f"vault/{uid}/fake_{filename}", len(data)

    def fake_signed_url(blob_path, minutes=60):
        return f"file://{blob_path}"

    monkeypatch.setattr(storage_service, "upload_user_file", fake_upload)
    monkeypatch.setattr(storage_service, "signed_download_url", fake_signed_url)

    access = await _login(client, fake_users)
    resp = await client.post(
        "/v1/vault/documents",
        files={"file": ("test.png", PNG_1KB, "image/png")},
        data={"docType": "aadhaar"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["downloadUrl"]
    assert body["sizeBytes"] == len(PNG_1KB)
    assert fake_db["users/uid-1/vault_documents"][body["id"]]["docType"] == "aadhaar"


async def test_reject_text_file_415(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.post(
        "/v1/vault/documents",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        data={"docType": "other"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 415
    assert resp.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


async def test_reject_oversize_413(client, fake_firebase, fake_users, fake_db, monkeypatch):
    from app.services import storage as storage_service

    monkeypatch.setattr(storage_service, "upload_user_file", lambda *a, **k: ("p", 0))
    access = await _login(client, fake_users)
    resp = await client.post(
        "/v1/vault/documents",
        files={"file": ("big.png", b"\x00" * (6 * 1024 * 1024), "image/png")},
        data={"docType": "other"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "FILE_TOO_LARGE"


async def test_delete_204_then_absent(client, fake_firebase, fake_users, fake_db, monkeypatch):
    from app.services import storage as storage_service

    monkeypatch.setattr(storage_service, "upload_user_file", lambda uid, data, filename, content_type, prefix="vault": (f"vault/{uid}/f", len(data)))
    monkeypatch.setattr(storage_service, "signed_download_url", lambda blob_path, minutes=60: f"file://{blob_path}")
    monkeypatch.setattr(storage_service, "delete_blob", lambda blob_path: None)
    access = await _login(client, fake_users)
    doc = (
        await client.post(
            "/v1/vault/documents",
            files={"file": ("test.png", PNG_1KB, "image/png")},
            data={"docType": "aadhaar"},
            headers=_auth_header(access),
        )
    ).json()

    resp = await client.delete(f"/v1/vault/documents/{doc['id']}", headers=_auth_header(access))
    assert resp.status_code == 204
    assert fake_db["users/uid-1/vault_documents"] == {}

    resp = await client.delete(f"/v1/vault/documents/{doc['id']}", headers=_auth_header(access))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"


async def test_logger_never_logs_bytes(client, fake_firebase, fake_users, fake_db, monkeypatch, caplog):
    from app.routers import vault as vault_router

    calls = []

    class SpyLogger:
        def __getattr__(self, name):
            return lambda *a, **k: calls.append((name, a, k))

    monkeypatch.setattr(vault_router, "logger", SpyLogger())
    access = await _login(client, fake_users)

    aadhaar_content = b"\x89PNG\r\n\x1a\n" + b"aadhaar 1234 5678 9012" + b"x" * 500
    await client.post(
        "/v1/vault/documents",
        files={"file": ("aadhaar.png", aadhaar_content, "image/png")},
        data={"docType": "aadhaar"},
        headers=_auth_header(access),
    )
    for _name, args, _kwargs in calls:
        assert aadhaar_content not in args
        assert not any("aadhaar 1234" in str(a) for a in args)
