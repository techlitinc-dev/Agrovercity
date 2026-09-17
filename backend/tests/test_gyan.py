from app.data.gyan_seed import seed_gyan
from app.services import coins as coins_service


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users, fake_db, coins=None) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    fake_users["users"]["uid-1"]["id"] = "uid-1"
    fake_db["users"]["uid-1"] = {"id": "uid-1", "agriCoins": coins or 0}
    return resp.json()["accessToken"]


async def test_workshops_list_not_enrolled(client, fake_firebase, fake_users, fake_db):
    await seed_gyan()
    access = await _login(client, fake_users, fake_db)
    resp = await client.get("/v1/workshops", headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json()["total"] == 3
    assert all(w["isEnrolled"] is False for w in resp.json()["data"])


async def test_enroll_fully_with_coins_201(client, fake_firebase, fake_users, fake_db):
    await seed_gyan()
    access = await _login(client, fake_users, fake_db, coins=500)
    fake_db["workshops"]["ws-test"] = {
        "id": "ws-test", "title": "Cheap course", "feeRupees": 200, "coinsDiscountAllowed": 200,
        "totalSeats": 50, "enrolledCount": 0, "batchDate": "2026-10-01",
    }
    resp = await client.post(
        "/v1/workshops/ws-test/enroll",
        json={"useCoins": True, "coinsToRedeem": 200},
        headers=_auth_header(access),
    )
    assert resp.status_code == 201
    assert resp.json()["enrolled"] is True
    assert fake_db["users"]["uid-1"]["agriCoins"] == 300
    assert fake_db["workshops"]["ws-test"]["enrolledCount"] == 1


async def test_enroll_twice_409(client, fake_firebase, fake_users, fake_db):
    await seed_gyan()
    access = await _login(client, fake_users, fake_db, coins=500)
    fake_db["workshops"]["ws-test"] = {"id": "ws-test", "feeRupees": 200, "coinsDiscountAllowed": 200, "totalSeats": 50, "enrolledCount": 0, "batchDate": "2026-10-01"}
    body = {"useCoins": True, "coinsToRedeem": 200}
    assert (await client.post("/v1/workshops/ws-test/enroll", json=body, headers=_auth_header(access))).status_code == 201
    resp = await client.post("/v1/workshops/ws-test/enroll", json=body, headers=_auth_header(access))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ALREADY_ENROLLED"


async def test_enroll_coins_over_cap_422(client, fake_firebase, fake_users, fake_db):
    await seed_gyan()
    access = await _login(client, fake_users, fake_db, coins=500)
    fake_db["workshops"]["ws-test"] = {"id": "ws-test", "feeRupees": 200, "coinsDiscountAllowed": 200, "totalSeats": 50, "enrolledCount": 0, "batchDate": "2026-10-01"}
    resp = await client.post(
        "/v1/workshops/ws-test/enroll",
        json={"useCoins": True, "coinsToRedeem": 250},
        headers=_auth_header(access),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_COIN_AMOUNT"


async def test_enroll_partial_coins_returns_razorpay_order(client, fake_firebase, fake_users, fake_db):
    await seed_gyan()
    access = await _login(client, fake_users, fake_db, coins=500)
    resp = await client.post(
        "/v1/workshops/ws-1/enroll",
        json={"useCoins": True, "coinsToRedeem": 200},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["enrolled"] is False
    assert body["paymentOrderId"].startswith("order_dev_")
    assert body["amountDue"] == 299


async def test_enroll_insufficient_coins_409(client, fake_firebase, fake_users, fake_db):
    await seed_gyan()
    access = await _login(client, fake_users, fake_db, coins=50)
    resp = await client.post(
        "/v1/workshops/ws-1/enroll",
        json={"useCoins": True, "coinsToRedeem": 200},
        headers=_auth_header(access),
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "INSUFFICIENT_COINS"
    assert resp.json()["error"]["message"] == "पर्याप्त कॉइन नहीं"


async def test_talk_register_awards_25(client, fake_firebase, fake_users, fake_db):
    await seed_gyan()
    access = await _login(client, fake_users, fake_db, coins=0)
    resp = await client.post("/v1/expert-talks/talk-1/register", headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json()["agriCoinsEarned"] == 25
    assert fake_db["users"]["uid-1"]["agriCoins"] == 25
    assert fake_db["expert_talks"]["talk-1"]["registeredCount"] == 211

    resp = await client.post("/v1/expert-talks/talk-1/register", headers=_auth_header(access))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ALREADY_REGISTERED"


async def test_blog_bookmark_toggles(client, fake_firebase, fake_users, fake_db):
    await seed_gyan()
    access = await _login(client, fake_users, fake_db)
    resp = await client.post("/v1/blogs/blog-1/bookmark", headers=_auth_header(access))
    assert resp.json()["isBookmarked"] is True
    resp = await client.post("/v1/blogs/blog-1/bookmark", headers=_auth_header(access))
    assert resp.json()["isBookmarked"] is False


async def test_blog_like_idempotent(client, fake_firebase, fake_users, fake_db):
    await seed_gyan()
    access = await _login(client, fake_users, fake_db)
    base = 124
    resp = await client.post("/v1/blogs/blog-1/like", headers=_auth_header(access))
    assert resp.json()["likesCount"] == base + 1
    resp = await client.post("/v1/blogs/blog-1/like", headers=_auth_header(access))
    assert resp.json()["likesCount"] == base + 1


async def test_spend_coins_insufficient_raises(client, fake_firebase, fake_users, fake_db):
    await _login(client, fake_users, fake_db, coins=10)
    import pytest

    with pytest.raises(coins_service.InsufficientCoins):
        await coins_service.spend_coins("uid-1", 100, "test")
