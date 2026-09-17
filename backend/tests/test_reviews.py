from app.data.livestock_seed import seed_livestock
from app.services.tokens import create_access_token


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users, uid="uid-1", name="Ramesh") -> str:
    if uid == "uid-1":
        resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
        assert resp.status_code == 200
        fake_users["users"]["uid-1"]["id"] = "uid-1"
        fake_users["users"]["uid-1"]["name"] = name
        return resp.json()["accessToken"]
    fake_users["users"][uid] = {"id": uid, "activeProfile": "farmer", "linkedProfiles": ["farmer"], "referralCode": f"ref_{uid[:8]}", "name": name}
    return create_access_token(uid)


async def _seed_product(client, fake_db, product_id="prod-1") -> dict:
    product = {
        "id": product_id,
        "title": "Hybrid seeds",
        "category": "seeds",
        "ratingAvg": None,
        "ratingCount": 0,
    }
    fake_db["products"][product_id] = product
    return product


async def test_post_review_updates_aggregate(client, fake_firebase, fake_users, fake_db):
    await _seed_product(client, fake_db)
    access_a = await _login(client, fake_users, "uid-1", "Ramesh")
    access_b = await _login(client, fake_users, "uid-2", "Suresh")

    await client.post(f"/v1/products/prod-1/reviews", json={"rating": 4, "comment": "good"}, headers=_auth_header(access_a))
    resp = await client.post(f"/v1/products/prod-1/reviews", json={"rating": 5, "comment": "excellent"}, headers=_auth_header(access_b))
    assert resp.status_code == 200
    assert resp.json()["rating"] == 5

    product = fake_db["products"]["prod-1"]
    assert product["ratingCount"] == 2
    assert product["ratingAvg"] == 4.5


async def test_upsert_same_user(client, fake_firebase, fake_users, fake_db):
    await _seed_product(client, fake_db)
    access = await _login(client, fake_users, "uid-1", "Ramesh")

    await client.post("/v1/products/prod-1/reviews", json={"rating": 3}, headers=_auth_header(access))
    resp = await client.post("/v1/products/prod-1/reviews", json={"rating": 5}, headers=_auth_header(access))
    assert resp.status_code == 200

    product = fake_db["products"]["prod-1"]
    assert product["ratingCount"] == 1
    assert product["ratingAvg"] == 5.0
    assert len(fake_db["products/prod-1/reviews"]) == 1


async def test_unknown_product_404(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, "uid-1", "Ramesh")
    resp = await client.post("/v1/products/nope/reviews", json={"rating": 5}, headers=_auth_header(access))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PRODUCT_NOT_FOUND"


async def test_rating_bounds_422(client, fake_firebase, fake_users, fake_db):
    await _seed_product(client, fake_db)
    access = await _login(client, fake_users, "uid-1", "Ramesh")
    for rating in ("0", "6"):
        resp = await client.post("/v1/products/prod-1/reviews", json={"rating": int(rating)}, headers=_auth_header(access))
        assert resp.status_code == 422


async def test_list_reviews_sorted(client, fake_firebase, fake_users, fake_db):
    await _seed_product(client, fake_db)
    access_a = await _login(client, fake_users, "uid-1", "Ramesh")
    access_b = await _login(client, fake_users, "uid-2", "Suresh")
    await client.post("/v1/products/prod-1/reviews", json={"rating": 4, "comment": "first"}, headers=_auth_header(access_a))
    await client.post("/v1/products/prod-1/reviews", json={"rating": 5, "comment": "second"}, headers=_auth_header(access_b))

    resp = await client.get("/v1/products/prod-1/reviews", headers=_auth_header(access_a))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 2
    assert data[0]["comment"] == "second"
    assert all(r["userName"] for r in data)
