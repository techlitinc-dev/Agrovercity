import pytest

from scripts.seed_mandi import build_history_rows


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    return resp.json()["accessToken"]


@pytest.fixture
def seeded_history(fake_db):
    for i, row in enumerate(build_history_rows()):
        fake_db["mandi_price_history"][f"hist-{i}"] = row
    return fake_db


async def test_history_default_3_months(client, fake_firebase, fake_users, seeded_history):
    access = await _login(client, fake_users)
    resp = await client.get(
        "/v1/mandi/prices/history",
        params={"crop": "tomato", "mandi": "Pimpalgaon"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 90
    dates = [d["date"] for d in data]
    assert dates == sorted(dates)


async def test_history_one_month(client, fake_firebase, fake_users, seeded_history):
    access = await _login(client, fake_users)
    resp = await client.get(
        "/v1/mandi/prices/history",
        params={"crop": "tomato", "mandi": "Pimpalgaon", "months": 1},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 30


async def test_history_unknown_crop(client, fake_firebase, fake_users, seeded_history):
    access = await _login(client, fake_users)
    resp = await client.get(
        "/v1/mandi/prices/history",
        params={"crop": "dragonfruit", "mandi": "Pimpalgaon"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    assert resp.json()["data"] == []


async def test_history_missing_params_422(client, fake_firebase, fake_users, seeded_history):
    access = await _login(client, fake_users)
    resp = await client.get("/v1/mandi/prices/history", headers=_auth_header(access))
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
