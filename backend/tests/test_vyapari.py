import pytest

from app.routers import mandi as mandi_router
from scripts.seed_mandi import MANDI_PRICES, VYAPARI_RATES


@pytest.fixture
def fake_cache(monkeypatch):
    store = {}

    async def fake_cache_get(key):
        return store.get(key)

    async def fake_cache_set(key, value, ttl_seconds):
        store[key] = value

    monkeypatch.setattr(mandi_router, "cache_get", fake_cache_get)
    monkeypatch.setattr(mandi_router, "cache_set", fake_cache_set)
    return store


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _seed(fake_db):
    for doc in MANDI_PRICES:
        fake_db["mandi_prices"][doc["id"]] = doc
    for doc in VYAPARI_RATES:
        fake_db["vyapari_rates"][doc["id"]] = doc


async def _login(client, fake_users, profile="farmer") -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    access = resp.json()["accessToken"]
    if profile != "farmer":
        fake_users["users"]["uid-1"]["activeProfile"] = profile
        fake_users["users"]["uid-1"]["id"] = "uid-1"
    return access


async def test_vyapari_rates_shape(client, fake_firebase, fake_users, fake_db, fake_cache):
    _seed(fake_db)
    access = await _login(client, fake_users)
    resp = await client.get("/v1/mandi/vyapari-rates", headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 3
    assert all(d["changeDir"] in {"up", "down", "flat"} for d in body["data"])
    assert "cachedAt" in body


async def test_vyapari_rates_cached(client, fake_firebase, fake_users, fake_db, fake_cache, monkeypatch):
    _seed(fake_db)
    access = await _login(client, fake_users)
    calls = 0
    original_query = mandi_router.db.query

    async def counting_query(collection, filters, limit=100):
        nonlocal calls
        calls += 1
        return await original_query(collection, filters, limit)

    monkeypatch.setattr(mandi_router.db, "query", counting_query)

    await client.get("/v1/mandi/vyapari-rates", headers=_auth_header(access))
    await client.get("/v1/mandi/vyapari-rates", headers=_auth_header(access))
    assert calls == 1


async def test_compare_ranks_by_net_profit(client, fake_firebase, fake_users, fake_db, fake_cache):
    _seed(fake_db)
    access = await _login(client, fake_users)
    resp = await client.get(
        "/v1/mandi/compare",
        params={"crop": "tomato", "quantityQuintals": 10, "lat": 20.0, "lng": 73.8},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert len(items) == 3
    profits = [item["netProfit"] for item in items]
    assert profits == sorted(profits, reverse=True)
    distances = {d["mandiName"]: d["distanceKm"] for d in MANDI_PRICES}
    for item in items:
        assert item["transportCost"] == distances[item["mandiName"]] * 12


async def test_compare_invalid_quantity(client, fake_firebase, fake_users, fake_db, fake_cache):
    _seed(fake_db)
    access = await _login(client, fake_users)
    resp = await client.get(
        "/v1/mandi/compare",
        params={"crop": "tomato", "quantityQuintals": 0},
        headers=_auth_header(access),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_QUANTITY"


async def test_seller_post_rate_pending(client, fake_firebase, fake_users, fake_db, fake_cache):
    _seed(fake_db)
    access = await _login(client, fake_users, profile="seller")
    resp = await client.post(
        "/v1/seller/rates",
        json={"crop": "Tomato", "ratePerKg": 24, "mandiName": "Nashik Mandi"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending"

    resp = await client.get("/v1/seller/rates/my", headers=_auth_header(access))
    assert resp.status_code == 200
    assert any(d["id"] == body["id"] for d in resp.json()["data"])


async def test_seller_rate_forbidden_for_farmer(client, fake_firebase, fake_users, fake_db, fake_cache):
    _seed(fake_db)
    access = await _login(client, fake_users, profile="farmer")
    resp = await client.post(
        "/v1/seller/rates",
        json={"crop": "Tomato", "ratePerKg": 24, "mandiName": "Nashik Mandi"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN_ROLE"


async def test_rate_within_band_accepted(client, fake_firebase, fake_users, fake_db, fake_cache):
    _seed(fake_db)
    access = await _login(client, fake_users, profile="seller")
    resp = await client.post(
        "/v1/seller/rates",
        json={"crop": "Tomato", "ratePerKg": 24, "mandiName": "Pimpalgaon Baswant APMC"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


async def test_rate_above_band_rejected(client, fake_firebase, fake_users, fake_db, fake_cache):
    _seed(fake_db)
    access = await _login(client, fake_users, profile="seller")
    resp = await client.post(
        "/v1/seller/rates",
        json={"crop": "Tomato", "ratePerKg": 40, "mandiName": "Nashik Mandi"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "RATE_OUT_OF_BAND"


async def test_rate_below_band_rejected(client, fake_firebase, fake_users, fake_db, fake_cache):
    _seed(fake_db)
    access = await _login(client, fake_users, profile="seller")
    resp = await client.post(
        "/v1/seller/rates",
        json={"crop": "Tomato", "ratePerKg": 10, "mandiName": "Nashik Mandi"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "RATE_OUT_OF_BAND"


async def test_rate_unknown_crop_accepted(client, fake_firebase, fake_users, fake_db, fake_cache):
    _seed(fake_db)
    access = await _login(client, fake_users, profile="seller")
    resp = await client.post(
        "/v1/seller/rates",
        json={"crop": "Dragonfruit", "ratePerKg": 90, "mandiName": "Nashik Mandi"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"
