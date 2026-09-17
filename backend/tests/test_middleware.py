import pytest

from app.core import cache


@pytest.fixture(autouse=True)
async def clear_rl_keys():
    try:
        redis = await cache.get_redis()
        keys = await redis.keys("rl:*")
        if keys:
            await redis.delete(*keys)
    except Exception:
        pass
    yield


async def test_101st_request_429(client):
    statuses = []
    last = None
    for _ in range(101):
        last = await client.get("/v1/news")
        statuses.append(last.status_code)
    assert all(s == 401 for s in statuses[:100])
    assert statuses[100] == 429
    assert last.json()["error"]["code"] == "RATE_LIMITED"
    assert "Retry-After" in last.headers


async def test_health_never_limited(client):
    for _ in range(105):
        resp = await client.get("/v1/health")
        assert resp.status_code == 200


async def test_request_id_header(client):
    resp = await client.get("/v1/health")
    assert resp.headers.get("X-Request-Id")


async def test_fail_open_on_redis_outage(client, monkeypatch):
    async def raising_get_redis():
        raise RuntimeError("redis down")

    monkeypatch.setattr(cache, "get_redis", raising_get_redis)
    resp = await client.get("/v1/health")
    assert resp.status_code == 200
    resp = await client.get("/v1/news")
    assert resp.status_code in (200, 401)
