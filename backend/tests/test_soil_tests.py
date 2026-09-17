def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


BOOK_BODY = {"plotId": None, "address": "Plot 12, Ozark village, Nashik district", "slot": "2026-09-20 am"}


async def _login(client, fake_users, uid="uid-1") -> str:
    if uid == "uid-1":
        resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
        assert resp.status_code == 200
        fake_users["users"]["uid-1"]["activeProfile"] = "farmer"
        fake_users["users"]["uid-1"]["id"] = "uid-1"
        return resp.json()["accessToken"]
    fake_users["users"][uid] = {"id": uid, "activeProfile": "farmer", "linkedProfiles": ["farmer"], "referralCode": f"ref_{uid[:8]}"}
    from app.services.tokens import create_access_token

    return create_access_token(uid)


async def test_book_201(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.post("/v1/soil-tests/book", json=BOOK_BODY, headers=_auth_header(access))
    assert resp.status_code == 201
    assert resp.json()["status"] == "booked"


async def test_double_book_same_plot_409(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    plot = (
        await client.post(
            "/v1/land/plots",
            json={"name": "P1", "village": "Ozark", "district": "Nashik", "areaAcres": 2},
            headers=_auth_header(access),
        )
    ).json()

    body = {**BOOK_BODY, "plotId": plot["id"]}
    assert (await client.post("/v1/soil-tests/book", json=body, headers=_auth_header(access))).status_code == 201
    resp = await client.post("/v1/soil-tests/book", json=body, headers=_auth_header(access))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "SOIL_TEST_ALREADY_BOOKED"


async def test_book_without_plot_ok(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.post("/v1/soil-tests/book", json=BOOK_BODY, headers=_auth_header(access))
    assert resp.status_code == 201


async def test_foreign_plot_404(client, fake_firebase, fake_users, fake_db):
    other = await _login(client, fake_users, "uid-2")
    plot = (
        await client.post(
            "/v1/land/plots",
            json={"name": "P2", "village": "Ozark", "district": "Nashik", "areaAcres": 2},
            headers=_auth_header(other),
        )
    ).json()

    access = await _login(client, fake_users)
    resp = await client.post("/v1/soil-tests/book", json={**BOOK_BODY, "plotId": plot["id"]}, headers=_auth_header(access))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PLOT_NOT_FOUND"


async def test_list_sorted_desc(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    await client.post("/v1/soil-tests/book", json={**BOOK_BODY, "slot": "2026-09-20 am"}, headers=_auth_header(access))
    await client.post("/v1/soil-tests/book", json={**BOOK_BODY, "slot": "2026-09-21 pm"}, headers=_auth_header(access))

    resp = await client.get("/v1/soil-tests", headers=_auth_header(access))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 2
    assert data[0]["bookedAt"] >= data[1]["bookedAt"]
