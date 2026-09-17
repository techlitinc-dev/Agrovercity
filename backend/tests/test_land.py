def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


PLOT_BODY = {"name": "Backyard field", "village": "Ozark", "district": "Nashik", "areaAcres": 3.5, "gatNumber": "112/2", "soilType": "Black Cotton"}


async def _login(client, fake_users) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    fake_users["users"]["uid-1"]["activeProfile"] = "farmLandlord"
    fake_users["users"]["uid-1"]["id"] = "uid-1"
    return resp.json()["accessToken"]


async def _create_plot(client, access) -> dict:
    resp = await client.post("/v1/land/plots", json=PLOT_BODY, headers=_auth_header(access))
    assert resp.status_code == 201
    return resp.json()


async def _create_lease(client, access, plot_id) -> dict:
    resp = await client.post(
        "/v1/land/leases",
        json={
            "plotId": plot_id,
            "tenantName": "Sunil Pawar",
            "tenantPhone": "+919822211122",
            "monthlyRentRupees": 8000,
            "startDate": "2026-07-01",
            "endDate": "2027-06-30",
        },
        headers=_auth_header(access),
    )
    assert resp.status_code == 201
    return resp.json()


async def test_create_plot_vacant(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    plot = await _create_plot(client, access)
    assert plot["status"] == "vacant"


async def test_create_lease_marks_plot_leased(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    plot = await _create_plot(client, access)
    lease = await _create_lease(client, access, plot["id"])
    assert lease["status"] == "active"

    plots = (await client.get("/v1/land/plots", headers=_auth_header(access))).json()["data"]
    assert plots[0]["status"] == "leased"


async def test_payment_and_duplicate_month_409(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    plot = await _create_plot(client, access)
    lease = await _create_lease(client, access, plot["id"])
    body = {"amountRupees": 8000, "month": "2026-09", "method": "upi", "paidAt": "2026-09-05T10:00:00Z"}

    resp = await client.post(f"/v1/land/leases/{lease['id']}/payments", json=body, headers=_auth_header(access))
    assert resp.status_code == 201

    resp = await client.post(f"/v1/land/leases/{lease['id']}/payments", json=body, headers=_auth_header(access))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "DUPLICATE_PAYMENT_MONTH"


async def test_payments_summary(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    plot = await _create_plot(client, access)
    lease = await _create_lease(client, access, plot["id"])
    await client.post(
        f"/v1/land/leases/{lease['id']}/payments",
        json={"amountRupees": 8000, "month": "2026-08", "method": "cash", "paidAt": "2026-08-05T10:00:00Z"},
        headers=_auth_header(access),
    )
    await client.post(
        f"/v1/land/leases/{lease['id']}/payments",
        json={"amountRupees": 8000, "month": "2026-09", "method": "upi", "paidAt": "2026-09-05T10:00:00Z"},
        headers=_auth_header(access),
    )

    resp = await client.get(f"/v1/land/leases/{lease['id']}/payments", headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["totalCollectedRupees"] == 16000
    assert "2026-08" not in body["pendingMonths"]
    assert "2026-09" not in body["pendingMonths"]
    assert len(body["pendingMonths"]) > 0


async def test_delete_plot_with_active_lease_409(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    plot = await _create_plot(client, access)
    lease = await _create_lease(client, access, plot["id"])
    _ = lease

    resp = await client.delete(f"/v1/land/plots/{plot['id']}", headers=_auth_header(access))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "PLOT_HAS_ACTIVE_LEASE"


async def test_end_lease_frees_plot(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    plot = await _create_plot(client, access)
    lease = await _create_lease(client, access, plot["id"])

    resp = await client.put(
        f"/v1/land/leases/{lease['id']}",
        json={"status": "ended"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200

    plots = (await client.get("/v1/land/plots", headers=_auth_header(access))).json()["data"]
    assert plots[0]["status"] == "vacant"


async def test_lease_bad_dates_422(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    plot = await _create_plot(client, access)
    resp = await client.post(
        "/v1/land/leases",
        json={
            "plotId": plot["id"],
            "tenantName": "Sunil Pawar",
            "tenantPhone": "+919822211122",
            "monthlyRentRupees": 8000,
            "startDate": "2027-06-30",
            "endDate": "2026-07-01",
        },
        headers=_auth_header(access),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
