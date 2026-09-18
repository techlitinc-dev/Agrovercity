import pytest

from app.data.rewards_seed import seed_rewards
from app.services import coins as coins_service


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users, fake_db, coins=0) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    fake_users["users"]["uid-1"]["id"] = "uid-1"
    fake_users["users"]["uid-1"]["name"] = "Ramesh"
    fake_db["users"]["uid-1"] = {"id": "uid-1", "agriCoins": coins}
    return resp.json()["accessToken"]


async def test_level_up_at_500(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db, coins=400)
    awarded = await coins_service.award_coins("uid-1", 600, "test_batch")
    assert awarded == 200
    user = fake_db["users"]["uid-1"]
    assert user["agriCoins"] == 600
    assert user["krishiRatnaLevel"] == 2
    assert user["krishiRatnaTitle"] == "Krishi Daksh"

    resp = await client.get("/v1/gamification/status", headers=_auth_header(access))
    assert resp.json()["xpToNextLevel"] == 900


async def test_redeem_voucher(client, fake_firebase, fake_users, fake_db):
    await seed_rewards()
    access = await _login(client, fake_users, fake_db, coins=600)
    resp = await client.post("/v1/gamification/redeem", json={"rewardId": "reward-iffco"}, headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["newBalance"] == 300
    assert body["couponCode"].startswith("KC-")


async def test_redeem_insufficient_409(client, fake_firebase, fake_users, fake_db):
    await seed_rewards()
    access = await _login(client, fake_users, fake_db, coins=300)
    resp = await client.post("/v1/gamification/redeem", json={"rewardId": "reward-video-call"}, headers=_auth_header(access))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "INSUFFICIENT_COINS"
    assert resp.json()["error"]["message"] == "पर्याप्त कॉइन नहीं"


async def test_ledger_signed_entries(client, fake_firebase, fake_users, fake_db):
    await seed_rewards()
    access = await _login(client, fake_users, fake_db, coins=300)
    await coins_service.award_coins("uid-1", 150, "diary_batch")
    resp = await client.post("/v1/gamification/redeem", json={"rewardId": "reward-iffco"}, headers=_auth_header(access))
    assert resp.status_code == 200

    amounts = [e["amount"] for e in fake_db["users/uid-1/coin_ledger"].values()]
    assert 150 in amounts
    assert -300 in amounts


async def test_invite_awards_100(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db, coins=0)
    resp = await client.post(
        "/v1/referrals/invite",
        json={"farmerName": "Sunil Pawar", "phone": "+919822211122"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 201
    assert resp.json()["agriCoinsEarned"] == 100

    resp = await client.post(
        "/v1/referrals/invite",
        json={"farmerName": "Sunil Pawar", "phone": "+919822211122"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ALREADY_INVITED"


async def test_referrals_milestones(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db, coins=0)
    await client.post(
        "/v1/referrals/invite",
        json={"farmerName": "Sunil Pawar", "phone": "+919822211122"},
        headers=_auth_header(access),
    )
    resp = await client.get("/v1/referrals", headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["referralCode"]
    assert body["milestones"][0]["achieved"] is True
    assert body["milestones"][1]["achieved"] is False
    assert body["milestones"][2]["achieved"] is False


async def test_daily_earn_cap_clamps(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db, coins=0)
    first = await coins_service.award_coins("uid-1", 150, "task1")
    second = await coins_service.award_coins("uid-1", 100, "task2")
    third = await coins_service.award_coins("uid-1", 100, "task3")
    assert first == 150
    assert second == 50
    assert third == 0
    assert fake_db["users"]["uid-1"]["agriCoins"] == 200
    capped = [e for e in fake_db["users/uid-1/coin_ledger"].values() if e["reason"].endswith("_capped")]
    assert len(capped) == 1
    _ = pytest


async def test_daily_redemption_cap(client, fake_firebase, fake_users, fake_db):
    await seed_rewards()
    access = await _login(client, fake_users, fake_db, coins=1000)
    resp = await client.post("/v1/gamification/redeem", json={"rewardId": "reward-iffco"}, headers=_auth_header(access))
    assert resp.status_code == 200

    fake_db["users"]["uid-1"]["agriCoins"] = 1000
    resp = await client.post("/v1/gamification/redeem", json={"rewardId": "reward-iffco"}, headers=_auth_header(access))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "REDEMPTION_LIMIT_REACHED"
    assert "रिडीम सीमा" in resp.json()["error"]["message"]


async def test_rewards_endpoint_paginates(client, fake_firebase, fake_users, fake_db):
    await seed_rewards()
    access = await _login(client, fake_users, fake_db, coins=0)

    resp = await client.get("/v1/gamification/rewards", headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == len(fake_db["rewards"])
    assert body["page"] == 1

    resp = await client.get(
        "/v1/gamification/rewards",
        params={"page": 2, "pageSize": 2},
        headers=_auth_header(access),
    )
    body = resp.json()
    assert len(body["data"]) == min(2, max(0, body["total"] - 2))
    assert body["pageSize"] == 2


async def test_ledger_endpoint_most_recent_first(client, fake_firebase, fake_users, fake_db):
    await seed_rewards()
    access = await _login(client, fake_users, fake_db, coins=600)
    await coins_service.award_coins("uid-1", 150, "diary_batch")
    resp = await client.post("/v1/gamification/redeem", json={"rewardId": "reward-iffco"}, headers=_auth_header(access))
    assert resp.status_code == 200

    resp = await client.get("/v1/gamification/ledger", headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    amounts = [e["amount"] for e in body["data"]]
    assert amounts[0] == -300
    assert set(amounts) == {150, -300}


async def test_ledger_endpoint_empty(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db, coins=0)
    resp = await client.get("/v1/gamification/ledger", headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []
    assert body["total"] == 0
