import json
from datetime import datetime, timezone
from uuid import uuid4

from app.core import cache, db

TTL_SECONDS = 86400
MAX_MESSAGES = 40


def _key(session_id: str) -> str:
    return f"chat:{session_id}"


async def append_message(session_id: str, uid: str, msg: dict) -> dict:
    doc = {"id": uuid4().hex, "userId": uid, **msg}
    redis = await cache.get_redis()
    await redis.rpush(_key(session_id), json.dumps(doc, ensure_ascii=False))
    await redis.ltrim(_key(session_id), -MAX_MESSAGES, -1)
    await redis.expire(_key(session_id), TTL_SECONDS)
    await db.set_subdoc_at(f"chat_sessions/{session_id}/messages", doc["id"], doc)
    return doc


async def get_history(session_id: str) -> list[dict]:
    redis = await cache.get_redis()
    raw = await redis.lrange(_key(session_id), 0, -1)
    if raw:
        return [json.loads(item) for item in raw]
    docs = await db.list_subdocs(f"chat_sessions/{session_id}/messages")
    docs.sort(key=lambda d: d.get("timestamp", ""))
    return docs
