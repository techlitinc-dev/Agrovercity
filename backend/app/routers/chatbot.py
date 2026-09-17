from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core import db
from app.core.deps import current_user_id
from app.models.chatbot import ChatMessageIn, HandoffIn, KisanMitraMessage
from app.services import chat_session as chat_session_service
from app.services import llm as llm_service
from app.services import users as users_service

router = APIRouter(prefix="/chatbot", tags=["chatbot"])

FALLBACK_TEXT = "अभी सेवा उपलब्ध नहीं है — थोड़ी देर बाद पूछें"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_llm_role(sender: str) -> str:
    return "user" if sender == "user" else "assistant"


@router.post("/messages")
async def send_message(body: ChatMessageIn, uid: str = Depends(current_user_id)):
    if not body.text and not body.audioUrl:
        raise HTTPException(
            status_code=400,
            detail={"code": "EMPTY_MESSAGE", "message": "Message text or audio is required", "fieldErrors": {}},
        )
    if body.text:
        text = body.text
    else:
        text = await llm_service.sarvam_stt(body.audioUrl, body.language)

    user_doc = await users_service.get_user(uid) or {}
    user_msg = {"sender": "user", "text": text, "timestamp": _now_iso()}
    await chat_session_service.append_message(body.sessionId, uid, user_msg)

    history = await chat_session_service.get_history(body.sessionId)
    llm_messages = [{"role": "system", "content": llm_service.build_system_prompt(user_doc)}] + [
        {"role": _to_llm_role(m.get("sender", "user")), "content": m.get("text", "")} for m in history
    ]
    try:
        bot_text = await llm_service.complete(llm_messages)
        card_type, card_data = llm_service.detect_rich_card(text)
    except llm_service.LLMUnavailable:
        bot_text = FALLBACK_TEXT
        card_type, card_data = None, None

    bot_msg = {
        "sender": "bot",
        "text": bot_text,
        "timestamp": _now_iso(),
        "quickReplies": llm_service.quick_replies_for(card_type),
        "richCardType": card_type,
        "richCardData": card_data,
    }
    bot_msg = await chat_session_service.append_message(body.sessionId, uid, bot_msg)
    return KisanMitraMessage(**bot_msg)


@router.get("/history")
async def history(sessionId: str = Query(...), page: int = 1, pageSize: int = 50, uid: str = Depends(current_user_id)):
    messages = await db.list_subdocs(f"chat_sessions/{sessionId}/messages")
    messages.sort(key=lambda m: m.get("timestamp", ""))
    total = len(messages)
    page_size = max(1, min(pageSize, 100))
    start = (max(1, page) - 1) * page_size
    return {"data": messages[start : start + page_size], "page": page, "pageSize": page_size, "total": total}


@router.post("/handoff")
async def handoff(body: HandoffIn, uid: str = Depends(current_user_id)):
    history = await chat_session_service.get_history(body.sessionId)
    thread_id = f"thread_{uuid4().hex[:10]}"
    await db.set_doc(
        "handoff_requests",
        uuid4().hex,
        {
            "userId": uid,
            "sessionId": body.sessionId,
            "reason": body.reason,
            "lastMessages": history[-10:],
            "createdAt": _now_iso(),
        },
    )
    await db.set_doc(
        "support_threads",
        thread_id,
        {
            "id": thread_id,
            "userId": uid,
            "sessionId": body.sessionId,
            "expertName": "डॉ. अनिता देशमुख (कृषि वैज्ञानिक)",
            "status": "open",
            "createdAt": _now_iso(),
            "lastMessageAt": _now_iso(),
        },
    )
    return {
        "expertName": "डॉ. अनिता देशमुख (कृषि वैज्ञानिक)",
        "contactChannel": "whatsapp",
        "etaMinutes": 30,
        "threadId": thread_id,
    }
