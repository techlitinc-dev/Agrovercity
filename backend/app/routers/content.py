from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.core import cache
from app.core import db
from app.core.deps import current_user_id
from app.models.content import ChatMessageIn, ChatMessageOut
from app.services import users as users_service

router = APIRouter(tags=["content"])


def _viewer_key(channel_id: str) -> str:
    return f"channel:{channel_id}:viewers"


@router.get("/news")
async def list_news(category: str | None = None, page: int = 1, pageSize: int = 20, user: dict = Depends(current_user_id)):
    docs = await db.query("news", [], limit=1000)
    if category:
        docs = [d for d in docs if d.get("category") == category]
    breaking = sorted([d for d in docs if d.get("isBreaking")], key=lambda d: d.get("timestamp", ""), reverse=True)
    rest = sorted([d for d in docs if not d.get("isBreaking")], key=lambda d: d.get("timestamp", ""), reverse=True)
    docs = breaking + rest
    total = len(docs)
    page_size = max(1, min(pageSize, 50))
    start = (max(1, page) - 1) * page_size
    return {"data": docs[start : start + page_size], "page": page, "pageSize": page_size, "total": total}


@router.get("/channels")
async def list_channels(user: dict = Depends(current_user_id)):
    docs = await db.query("channels", [], limit=1000)
    redis = await cache.get_redis()
    for doc in docs:
        viewers = await redis.get(_viewer_key(doc["id"]))
        if viewers is not None:
            doc["liveViewersCount"] = int(viewers)
    return {"data": docs, "page": 1, "pageSize": 50, "total": len(docs)}


def _chat_path(channel_id: str) -> str:
    return f"channels/{channel_id}/chat"


async def _channel_or_404(channel_id: str) -> dict:
    channel = await db.get_doc("channels", channel_id)
    if channel is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "CHANNEL_NOT_FOUND", "message": "Channel not found", "fieldErrors": {}},
        )
    return channel


@router.get("/channels/{channel_id}/chat")
async def get_chat(channel_id: str, uid: str = Depends(current_user_id)):
    await _channel_or_404(channel_id)
    from app.services.blocks import list_blocked_ids

    blocked = await list_blocked_ids(uid)
    messages = await db.list_subdocs(_chat_path(channel_id))
    messages = [m for m in messages if m.get("userId") not in blocked]
    messages.sort(key=lambda m: m.get("sentAt", ""), reverse=True)
    messages = list(reversed(messages[-50:]))
    return {"data": messages, "page": 1, "pageSize": 50, "total": len(messages)}


@router.post("/channels/{channel_id}/chat", status_code=201)
async def post_chat(
    channel_id: str,
    body: ChatMessageIn | None = None,
    joined: bool = False,
    left: bool = False,
    uid: str = Depends(current_user_id),
):
    await _channel_or_404(channel_id)
    redis = await cache.get_redis()

    if joined:
        await redis.incr(_viewer_key(channel_id))
    if left:
        viewers = int(await redis.decr(_viewer_key(channel_id)))
        if viewers < 0:
            await redis.set(_viewer_key(channel_id), 0)

    if body is None:
        return {"ok": True}

    user = await users_service.get_user(uid)
    user_name = (user or {}).get("name") or "Farmer"
    rate_key = f"ratelimit:chat:{uid}:{channel_id}"
    set_result = await redis.set(rate_key, 1, ex=2, nx=True)
    if not set_result:
        raise HTTPException(
            status_code=429,
            detail={"code": "CHAT_RATE_LIMITED", "message": "थोड़ा धीरे भेजें", "fieldErrors": {}},
        )
    message_id = uuid4().hex
    doc = {
        "id": message_id,
        "userId": uid,
        "userName": user_name,
        "text": body.text,
        "sentAt": datetime.now(timezone.utc).isoformat(),
    }
    await db.set_subdoc_at(_chat_path(channel_id), message_id, doc)
    return ChatMessageOut(**doc)
