from scripts.seed_contracts import CONTRACTS


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users, profile="farmer") -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    access = resp.json()["accessToken"]
    fake_users["users"]["uid-1"]["activeProfile"] = profile
    fake_users["users"]["uid-1"]["id"] = "uid-1"
    return access


async def _seed_contracts(fake_db):
    for doc in CONTRACTS:
        fake_db["contracts"][doc["id"]] = doc


async def test_list_contracts(client, fake_firebase, fake_users, fake_db):
    await _seed_contracts(fake_db)
    access = await _login(client, fake_users)
    resp = await client.get("/v1/contracts", headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json()["total"] == 3

    resp = await client.get("/v1/contracts", params={"status": "open"}, headers=_auth_header(access))
    assert resp.json()["total"] == 3


async def test_detail_includes_terms(client, fake_firebase, fake_users, fake_db):
    await _seed_contracts(fake_db)
    access = await _login(client, fake_users)
    resp = await client.get("/v1/contracts/contract-1", headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json()["termsText"]


async def test_accept_success(client, fake_firebase, fake_users, fake_db):
    await _seed_contracts(fake_db)
    access = await _login(client, fake_users)
    resp = await client.post("/v1/auth/mpin/set", json={"mpin": "1234"}, headers=_auth_header(access))
    assert resp.status_code == 200

    resp = await client.post(
        "/v1/contracts/contract-1/accept",
        json={"signatureData": "base64png", "consentTimestamp": "2026-09-17T00:00:00Z", "mpin": "1234"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"

    assert fake_db["contracts"]["contract-1"]["status"] == "accepted"
    assert fake_db["contracts"]["contract-1"]["acceptedBy"] == "uid-1"
    acceptance = fake_db["contracts/contract-1/acceptances"]["uid-1"]
    assert acceptance["signatureData"] == "base64png"


async def test_accept_wrong_mpin(client, fake_firebase, fake_users, fake_db):
    await _seed_contracts(fake_db)
    access = await _login(client, fake_users)
    await client.post("/v1/auth/mpin/set", json={"mpin": "1234"}, headers=_auth_header(access))

    resp = await client.post(
        "/v1/contracts/contract-1/accept",
        json={"signatureData": "base64png", "consentTimestamp": "2026-09-17T00:00:00Z", "mpin": "9999"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "WRONG_MPIN"


async def test_accept_already_accepted(client, fake_firebase, fake_users, fake_db):
    await _seed_contracts(fake_db)
    access = await _login(client, fake_users)
    await client.post("/v1/auth/mpin/set", json={"mpin": "1234"}, headers=_auth_header(access))
    body = {"signatureData": "base64png", "consentTimestamp": "2026-09-17T00:00:00Z", "mpin": "1234"}

    resp = await client.post("/v1/contracts/contract-1/accept", json=body, headers=_auth_header(access))
    assert resp.status_code == 200
    resp = await client.post("/v1/contracts/contract-1/accept", json=body, headers=_auth_header(access))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONTRACT_NOT_OPEN"


async def test_accept_broker_forbidden(client, fake_firebase, fake_users, fake_db):
    await _seed_contracts(fake_db)
    access = await _login(client, fake_users, profile="broker")
    resp = await client.post(
        "/v1/contracts/contract-1/accept",
        json={"signatureData": "base64png", "consentTimestamp": "2026-09-17T00:00:00Z", "mpin": "1234"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN_ROLE"
