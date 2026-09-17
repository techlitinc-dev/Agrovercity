def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users, profile="farmer") -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    fake_users["users"]["uid-1"]["activeProfile"] = profile
    fake_users["users"]["uid-1"]["id"] = "uid-1"
    return resp.json()["accessToken"]


async def test_shg_seeds_defaults_on_first_read(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.get("/v1/women/shg", headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["memberCount"] == 12
    assert body["corpus"] == 48500
    assert body["loanFund"] == 30000
    assert body["monthlyDeposit"] == 500


async def test_deposit_updates_corpus(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    await client.get("/v1/women/shg", headers=_auth_header(access))
    resp = await client.post("/v1/women/shg/deposit", json={"amount": 500, "month": "2026-09"}, headers=_auth_header(access))
    assert resp.status_code == 201
    assert resp.json() == {"deposited": 500, "newCorpus": 49000}


async def test_duplicate_deposit_month_409(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    await client.get("/v1/women/shg", headers=_auth_header(access))
    body = {"amount": 500, "month": "2026-09"}
    assert (await client.post("/v1/women/shg/deposit", json=body, headers=_auth_header(access))).status_code == 201
    resp = await client.post("/v1/women/shg/deposit", json=body, headers=_auth_header(access))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "DUPLICATE_DEPOSIT_MONTH"


async def test_home_enterprise_total(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.get("/v1/women/home-enterprise", headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["totalMonthlyProfit"] == sum(line["monthlyProfit"] for line in body["lines"]) == 9800


async def test_deposit_bad_month_format_422(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    await client.get("/v1/women/shg", headers=_auth_header(access))
    resp = await client.post("/v1/women/shg/deposit", json={"amount": 500, "month": "Sep 2026"}, headers=_auth_header(access))
    assert resp.status_code == 422


async def test_women_forbidden_for_seller(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, profile="seller")
    resp = await client.get("/v1/women/shg", headers=_auth_header(access))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN_ROLE"
