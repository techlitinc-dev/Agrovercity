import pytest

from app.routers import weather as weather_router


@pytest.fixture
def fake_cache(monkeypatch):
    store = {}

    async def fake_cache_get(key):
        return store.get(key)

    async def fake_cache_set(key, value, ttl_seconds):
        store[key] = value

    monkeypatch.setattr(weather_router, "cache_get", fake_cache_get)
    monkeypatch.setattr(weather_router, "cache_set", fake_cache_set)
    return store


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    return resp.json()["accessToken"]


async def test_weather_shape(client, fake_firebase, fake_users, fake_cache):
    access = await _login(client)
    resp = await client.get("/v1/weather", params={"lat": 20.0, "lng": 73.8}, headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    for key in ("tempC", "rainProbability", "condition", "radarAvailable", "forecast"):
        assert key in body


async def test_weather_caches(client, fake_firebase, fake_users, fake_cache, monkeypatch):
    access = await _login(client)
    calls = []

    async def counting_fetch(lat, lng):
        calls.append((lat, lng))
        return {"tempC": 31, "rainProbability": 40, "condition": "Partly Cloudy", "radarAvailable": True, "forecast": []}

    monkeypatch.setattr(weather_router, "fetch_weather", counting_fetch)

    await client.get("/v1/weather", params={"lat": 20.0, "lng": 73.8}, headers=_auth_header(access))
    await client.get("/v1/weather", params={"lat": 20.0, "lng": 73.8}, headers=_auth_header(access))
    assert len(calls) == 1

    await client.get("/v1/weather", params={"lat": 21.0, "lng": 73.8}, headers=_auth_header(access))
    assert len(calls) == 2


async def test_weather_requires_auth(client, fake_firebase, fake_users):
    resp = await client.get("/v1/weather", params={"lat": 20.0, "lng": 73.8})
    assert resp.status_code == 401
