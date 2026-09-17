import httpx
import pytest
import redis.asyncio as aioredis

from app.core.cache import cache_delete, cache_get, cache_set
from app.core.config import settings
from app.main import app


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def test_settings_load():
    assert settings.jwt_algorithm == "HS256"


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_cache_roundtrip():
    try:
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        await r.ping()
        await r.aclose()
    except Exception:
        pytest.skip("Redis not reachable")

    key = "test:k"
    await cache_set(key, "v", 60)
    assert await cache_get(key) == "v"
    await cache_delete(key)
    assert await cache_get(key) is None
