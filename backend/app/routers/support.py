from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core import db
from app.core.deps import current_user_id

router = APIRouter(prefix="/support", tags=["support"])


def _threads_path() -> str:
    return "support_threads"


def _messages_path(thread_id: str) -> str:
    return f"support_threads/{thread_id}/messages"


class SupportMessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


async def _get_own_thread(thread_id: str, uid: str) -> dict:
    thread = await db.get_doc(_threads_path(), thread_id)
    if thread is None or thread.get("userId") != uid:
        raise HTTPException(
            status_code=404,
            detail={"code": "THREAD_NOT_FOUND", "message": "Thread not found", "fieldErrors": {}},
        )
    return thread


@router.get("/threads")
async def list_threads(page: int = 1, pageSize: int = 20, uid: str = Depends(current_user_id)):
    threads = await db.query("support_threads", [("userId", "==", uid)], limit=1000)
    threads.sort(key=lambda t: t.get("lastMessageAt", ""), reverse=True)
    total = len(threads)
    page_size = max(1, min(pageSize, 50))
    start = (max(1, page) - 1) * page_size
    return {"data": threads[start : start + page_size], "page": page, "pageSize": page_size, "total": total}


@router.get("/threads/{thread_id}/messages")
async def list_messages(thread_id: str, page: int = 1, pageSize: int = 50, uid: str = Depends(current_user_id)):
    await _get_own_thread(thread_id, uid)
    messages = await db.list_subdocs(_messages_path(thread_id))
    messages.sort(key=lambda m: m.get("at", ""))
    total = len(messages)
    page_size = max(1, min(pageSize, 100))
    start = (max(1, page) - 1) * page_size
    return {"data": messages[start : start + page_size], "page": page, "pageSize": page_size, "total": total}


@router.post("/threads/{thread_id}/messages", status_code=201)
async def post_message(thread_id: str, body: SupportMessageIn, uid: str = Depends(current_user_id)):
    await _get_own_thread(thread_id, uid)
    message_id = uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    doc = {"id": message_id, "sender": "user", "text": body.text, "at": now}
    await db.set_subdoc_at(_messages_path(thread_id), message_id, doc)
    thread = await db.get_doc(_threads_path(), thread_id)
    if thread is not None:
        thread["lastMessageAt"] = now
        await db.set_doc(_threads_path(), thread_id, thread)
    return doc
