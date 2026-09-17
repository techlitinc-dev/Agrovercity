def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users, fake_db=None, profile="farmer") -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    fake_users["users"]["uid-1"]["activeProfile"] = profile
    fake_users["users"]["uid-1"]["id"] = "uid-1"
    return resp.json()["accessToken"]


async def test_credit_score_defaults(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db)
    resp = await client.get("/v1/finance/credit-score", headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["kisanCreditScore"] == 650
    assert body["creditTier"] == "Silver"
    assert body["creditLimit"] == 50000
    assert body["factors"]


async def test_emi_exact(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db)
    resp = await client.post(
        "/v1/finance/loan-calculator",
        json={"amount": 25000, "tenureMonths": 6, "interestRate": 7},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    body = resp.json()
    # Day file's quoted 4256.44 does not match its own formula; the exact
    # standard-formula EMI for 25000/6/7% is 4252.15 — asserted here.
    assert abs(body["emi"] - 4252.15) < 0.5
    assert body["totalInterest"] == round(body["totalPayable"] - 25000, 2)


async def test_amount_below_min_422(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db)
    resp = await client.post(
        "/v1/finance/loan-calculator",
        json={"amount": 4000, "tenureMonths": 6},
        headers=_auth_header(access),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    resp = await client.post(
        "/v1/finance/loan-calculator",
        json={"amount": 25000, "tenureMonths": 13},
        headers=_auth_header(access),
    )
    assert resp.status_code == 422


async def test_kcc_not_found(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db)
    resp = await client.get("/v1/finance/kcc", headers=_auth_header(access))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "KCC_NOT_FOUND"


async def test_loan_apply(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db)
    resp = await client.post(
        "/v1/finance/loans/apply",
        json={"amount": 50000, "tenureMonths": 12, "purpose": "Tractor purchase"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["applicationId"]
    assert body["status"] == "submitted"


async def test_loans_list_after_apply(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db)
    await client.post(
        "/v1/finance/loans/apply",
        json={"amount": 50000, "tenureMonths": 12, "purpose": "Tractor purchase"},
        headers=_auth_header(access),
    )
    resp = await client.get("/v1/finance/loans", headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["data"][0]["status"] == "submitted"
    assert body["data"][0]["applicationId"]


async def test_loans_empty_list_200(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db)
    resp = await client.get("/v1/finance/loans", headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json()["data"] == []
