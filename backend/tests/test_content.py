from app.core import cache
from app.data.content_seed import seed_content


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    fake_users["users"]["uid-1"]["id"] = "uid-1"
    fake_users["users"]["uid-1"]["name"] = "Ramesh"
    return resp.json()["accessToken"]


async def test_news_breaking_first(client, fake_firebase, fake_users, fake_db):
    await seed_content()
    access = await _login(client, fake_users)
    resp = await client.get("/v1/news", headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 6
    assert body["data"][0]["isBreaking"] is True


async def test_news_category_filter(client, fake_firebase, fake_users, fake_db):
    await seed_content()
    access = await _login(client, fake_users)
    resp = await client.get("/v1/news", params={"category": "weather-alert"}, headers=_auth_header(access))
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["category"] == "weather-alert"


async def test_channels_viewer_count_from_redis(client, fake_firebase, fake_users, fake_db):
    await seed_content()
    redis = await cache.get_redis()
    await redis.set("channel:ch-1:viewers", 42)
    access = await _login(client, fake_users)

    resp = await client.get("/v1/channels", headers=_auth_header(access))
    data = resp.json()["data"]
    ch1 = next(c for c in data if c["id"] == "ch-1")
    assert ch1["liveViewersCount"] == 42
    ch2 = next(c for c in data if c["id"] == "ch-2")
    assert ch2["liveViewersCount"] != 42
    assert ch2["streamUrl"].endswith(".m3u8")
    await redis.delete("channel:ch-1:viewers")


async def test_chat_post_and_rate_limit(client, fake_firebase, fake_users, fake_db):
    await seed_content()
    access = await _login(client, fake_users)
    redis = await cache.get_redis()
    await redis.delete("ratelimit:chat:uid-1:ch-1")

    resp = await client.post("/v1/channels/ch-1/chat", json={"text": "नमस्ते"}, headers=_auth_header(access))
    assert resp.status_code == 201
    assert resp.json()["userName"] == "Ramesh"

    resp = await client.post("/v1/channels/ch-1/chat", json={"text": "again"}, headers=_auth_header(access))
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "CHAT_RATE_LIMITED"
    await redis.delete("ratelimit:chat:uid-1:ch-1")


async def test_chat_unknown_channel_404(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.post("/v1/channels/nope/chat", json={"text": "hi"}, headers=_auth_header(access))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CHANNEL_NOT_FOUND"


async def test_viewer_join_left(client, fake_firebase, fake_users, fake_db):
    await seed_content()
    access = await _login(client, fake_users)
    redis = await cache.get_redis()
    await redis.delete("channel:ch-1:viewers")

    await client.post("/v1/channels/ch-1/chat", params={"joined": "true"}, json={"text": "hi"}, headers=_auth_header(access))
    await client.post("/v1/channels/ch-1/chat", params={"joined": "true"}, json={"text": "hi"}, headers=_auth_header(access))
    await client.post("/v1/channels/ch-1/chat", params={"left": "true"}, json={"text": "bye"}, headers=_auth_header(access))

    assert int(await redis.get("channel:ch-1:viewers")) == 1
    await redis.delete("channel:ch-1:viewers", "ratelimit:chat:uid-1:ch-1")
