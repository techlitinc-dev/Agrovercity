import pytest

from app.data.rewards_seed import seed_rewards
from app.services import coins as coins_service


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users, fake_db, coins=0) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    fake_users["users"]["uid-1"]["id"] = "uid-1"
    fake_users["users"]["uid-1"]["activeProfile"] = "farmer"
    fake_db["users"]["uid-1"] = {"id": "uid-1", "agriCoins": coins}
    return resp.json()["accessToken"]


async def test_422_envelope(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db)
    resp = await client.post("/v1/pnl/break-even", json={}, headers=_auth_header(access))
    assert resp.status_code == 422
    error = resp.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["message"]
    assert error["fieldErrors"]


async def test_404_envelope(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, fake_db)
    resp = await client.get("/v1/insurance/claims/nope", headers=_auth_header(access))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CLAIM_NOT_FOUND"


async def test_409_envelope(client, fake_firebase, fake_users, fake_db):
    await seed_rewards()
    access = await _login(client, fake_users, fake_db, coins=100)
    resp = await client.post("/v1/gamification/redeem", json={"rewardId": "reward-video-call"}, headers=_auth_header(access))
    assert resp.status_code == 409
    error = resp.json()["error"]
    assert error["code"] == "INSUFFICIENT_COINS"
    assert error["message"] == "पर्याप्त कॉइन नहीं"


async def test_429_envelope(client, fake_firebase, fake_users, fake_db):
    last = None
    for _ in range(101):
        last = await client.get("/v1/news")
    assert last.status_code == 429
    error = last.json()["error"]
    assert error["code"] == "RATE_LIMITED"
    assert error["message"]
    assert error["fieldErrors"] == {}


async def test_500_envelope():
    import httpx

    from app.main import app

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/v1/debug/sentry-test")
    assert resp.status_code == 500
    error = resp.json()["error"]
    assert error["code"] == "INTERNAL_ERROR"
    assert error["message"] == "Something went wrong"
    assert error["fieldErrors"] == {}
    assert "Traceback" not in resp.text
