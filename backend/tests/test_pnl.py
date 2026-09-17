def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    fake_users["users"]["uid-1"]["activeProfile"] = "farmer"
    fake_users["users"]["uid-1"]["id"] = "uid-1"
    return resp.json()["accessToken"]


async def test_summary_empty_user_zeros(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.get("/v1/pnl/summary", headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json() == {"grossIncome": 0, "productionCost": 0, "netProfit": 0}


async def test_crops_seeds_demo_on_first_read(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.get("/v1/pnl/crops", headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    names = {c["name"] for c in body["data"]}
    assert names == {"Wheat", "Onion"}
    assert "users/uid-1/crop_pnl" in fake_db


async def test_add_expense_recomputes(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    crops = (await client.get("/v1/pnl/crops", headers=_auth_header(access))).json()["data"]
    wheat = next(c for c in crops if c["name"] == "Wheat")
    old_total = wheat["totalExpenses"]

    resp = await client.post(
        f"/v1/pnl/crops/{wheat['id']}/expenses",
        json={"category": "transport", "amount": 5000},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["totalExpenses"] == old_total + 5000
    assert body["netProfit"] == body["grossRevenue"] - body["totalExpenses"]


async def test_break_even_exact(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.post(
        "/v1/pnl/break-even",
        json={"totalCost": 50000, "expectedYieldQuintals": 20},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    assert resp.json() == {"minSafePricePerQuintal": 2500}


async def test_break_even_zero_yield_422(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.post(
        "/v1/pnl/break-even",
        json={"totalCost": 50000, "expectedYieldQuintals": 0},
        headers=_auth_header(access),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
