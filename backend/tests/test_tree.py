from app.data.tree_seed import seed_tree


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    fake_users["users"]["uid-1"]["activeProfile"] = "farmer"
    fake_users["users"]["uid-1"]["id"] = "uid-1"
    return resp.json()["accessToken"]


async def test_care_guides_sorted(client, fake_firebase, fake_users, fake_db):
    await seed_tree()
    access = await _login(client, fake_users)
    resp = await client.get("/v1/tree/care-guides", headers=_auth_header(access))
    assert resp.status_code == 200
    steps = [g["stepNumber"] for g in resp.json()["data"]]
    assert steps == [1, 2, 3, 4, 5]


async def test_sapling_request_201(client, fake_firebase, fake_users, fake_db):
    await seed_tree()
    access = await _login(client, fake_users)
    resp = await client.post(
        "/v1/tree/ngos/ngo-1/sapling-request",
        json={"treeType": "fruit", "count": 50},
        headers=_auth_header(access),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "requested"
    assert "users/uid-1/sapling_requests" in fake_db


async def test_sapling_count_over_500_422(client, fake_firebase, fake_users, fake_db):
    await seed_tree()
    access = await _login(client, fake_users)
    resp = await client.post(
        "/v1/tree/ngos/ngo-1/sapling-request",
        json={"treeType": "timber", "count": 501},
        headers=_auth_header(access),
    )
    assert resp.status_code == 422


async def test_unknown_ngo_404(client, fake_firebase, fake_users, fake_db):
    await seed_tree()
    access = await _login(client, fake_users)
    resp = await client.post(
        "/v1/tree/ngos/nope/sapling-request",
        json={"treeType": "bamboo", "count": 10},
        headers=_auth_header(access),
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NGO_NOT_FOUND"
