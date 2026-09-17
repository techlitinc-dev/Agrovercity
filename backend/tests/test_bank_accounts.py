def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


ACCOUNT_BODY = {"accountHolder": "Ram Singh", "accountNumber": "12345678901", "ifsc": "SBIN0001234", "bankName": "SBI"}


async def _login(client, fake_users, uid="uid-1") -> str:
    if uid == "uid-1":
        resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
        assert resp.status_code == 200
        fake_users["users"]["uid-1"]["id"] = "uid-1"
        return resp.json()["accessToken"]
    fake_users["users"][uid] = {"id": uid, "activeProfile": "farmer", "linkedProfiles": ["farmer"], "referralCode": f"ref_{uid[:8]}"}
    from app.services.tokens import create_access_token

    return create_access_token(uid)


async def _create_account(client, access, **overrides) -> dict:
    resp = await client.post("/v1/bank-accounts", json={**ACCOUNT_BODY, **overrides}, headers=_auth_header(access))
    assert resp.status_code == 201
    return resp.json()


async def test_first_account_becomes_primary(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    account = await _create_account(client, access)
    assert account["isPrimary"] is True
    assert account["verifyStatus"] == "unverified"
    assert account["accountNumberMasked"] == "XXXX8901"
    assert "12345678901" not in str(account)


async def test_bad_ifsc_422(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.post("/v1/bank-accounts", json={**ACCOUNT_BODY, "ifsc": "SBIN1234"}, headers=_auth_header(access))
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_short_account_number_422(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.post("/v1/bank-accounts", json={**ACCOUNT_BODY, "accountNumber": "12345"}, headers=_auth_header(access))
    assert resp.status_code == 422


async def test_verify_stub_success(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    account = await _create_account(client, access)
    resp = await client.post(f"/v1/bank-accounts/{account['id']}/verify", headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json()["verifyStatus"] == "verified"


async def test_set_primary_flips_flags(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    first = await _create_account(client, access)
    second = await _create_account(client, access, accountHolder="Ram Singh 2", accountNumber="12345678902")

    resp = await client.post(f"/v1/bank-accounts/{second['id']}/set-primary", headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json()["primaryId"] == second["id"]

    accounts = (await client.get("/v1/bank-accounts", headers=_auth_header(access))).json()["data"]
    flags = {a["id"]: a["isPrimary"] for a in accounts}
    assert flags[first["id"]] is False
    assert flags[second["id"]] is True


async def test_delete_primary_promotes_oldest(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    first = await _create_account(client, access)
    second = await _create_account(client, access, accountHolder="Ram Singh 2", accountNumber="12345678902")

    resp = await client.delete(f"/v1/bank-accounts/{first['id']}", headers=_auth_header(access))
    assert resp.status_code == 204

    accounts = (await client.get("/v1/bank-accounts", headers=_auth_header(access))).json()["data"]
    assert len(accounts) == 1
    assert accounts[0]["id"] == second["id"]
    assert accounts[0]["isPrimary"] is True


async def test_foreign_account_404(client, fake_firebase, fake_users, fake_db):
    access_a = await _login(client, fake_users)
    account = await _create_account(client, access_a)
    access_b = await _login(client, fake_users, uid="uid-2")

    resp = await client.post(f"/v1/bank-accounts/{account['id']}/verify", headers=_auth_header(access_b))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "BANK_ACCOUNT_NOT_FOUND"

    resp = await client.delete(f"/v1/bank-accounts/{account['id']}", headers=_auth_header(access_b))
    assert resp.status_code == 404
