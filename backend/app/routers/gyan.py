import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.core import db
from app.core.deps import current_user_id
from app.models.gyan import EnrollIn, QuestionIn
from app.services import coins as coins_service
from app.services.payments import create_razorpay_order

router = APIRouter(tags=["gyan"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _enroll_path(uid: str) -> str:
    return f"users/{uid}/workshop_enrollments"


def _envelope(data: list[dict], page: int, page_size: int) -> dict:
    total = len(data)
    start = (max(1, page) - 1) * page_size
    return {"data": data[start : start + page_size], "page": page, "pageSize": page_size, "total": total}


def _page_size(pageSize: int) -> int:
    return max(1, min(pageSize, 50))


@router.get("/workshops")
async def list_workshops(page: int = 1, pageSize: int = 20, uid: str = Depends(current_user_id)):
    workshops = await db.query("workshops", [], limit=1000)
    workshops.sort(key=lambda w: w.get("batchDate", ""))
    enrollments = {d["id"]: d for d in await db.list_subdocs(_enroll_path(uid))}
    items = []
    for w in workshops:
        enrollment = enrollments.get(w["id"])
        items.append({**w, "isEnrolled": bool(enrollment and enrollment.get("status") == "enrolled")})
    return _envelope(items, page, _page_size(pageSize))


@router.post("/workshops/{workshop_id}/enroll")
async def enroll_workshop(workshop_id: str, body: EnrollIn, uid: str = Depends(current_user_id)):
    workshop = await db.get_doc("workshops", workshop_id)
    if workshop is None:
        raise HTTPException(status_code=404, detail={"code": "WORKSHOP_NOT_FOUND", "message": "Workshop not found", "fieldErrors": {}})
    if workshop.get("enrolledCount", 0) >= workshop.get("totalSeats", 0):
        raise HTTPException(status_code=409, detail={"code": "WORKSHOP_FULL", "message": "सीटें भर गईं", "fieldErrors": {}})
    enrollment_path = _enroll_path(uid)
    existing = await db.get_subdoc_at(enrollment_path, workshop_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail={"code": "ALREADY_ENROLLED", "message": "पहले से नामांकित", "fieldErrors": {}})

    fee = workshop.get("feeRupees", 0)
    coins_to_redeem = 0
    if body.useCoins:
        coins_to_redeem = body.coinsToRedeem
        if coins_to_redeem <= 0 or coins_to_redeem > workshop.get("coinsDiscountAllowed", 0) or coins_to_redeem > fee:
            raise HTTPException(
                status_code=422,
                detail={"code": "INVALID_COIN_AMOUNT", "message": "Invalid coin redemption amount", "fieldErrors": {"coinsToRedeem": f"1–{min(workshop.get('coinsDiscountAllowed', 0), fee)}"}},
            )
        try:
            await coins_service.spend_coins(uid, coins_to_redeem, "workshop_discount", workshop_id)
        except coins_service.InsufficientCoins:
            raise HTTPException(status_code=409, detail={"code": "INSUFFICIENT_COINS", "message": "पर्याप्त कॉइन नहीं", "fieldErrors": {}})

    remaining = round(fee - coins_to_redeem, 2)
    if remaining > 0:
        order = create_razorpay_order(int(remaining * 100), f"ws-{workshop_id}-{uid[:8]}")
        await db.set_subdoc_at(
            enrollment_path,
            workshop_id,
            {"id": workshop_id, "status": "awaiting_payment", "razorpayOrderId": order["id"], "amountDue": remaining, "createdAt": _now_iso()},
        )
        return {"enrolled": False, "paymentOrderId": order["id"], "amountDue": remaining}

    await db.set_subdoc_at(enrollment_path, workshop_id, {"id": workshop_id, "status": "enrolled", "enrolledAt": _now_iso()})
    workshop["enrolledCount"] = workshop.get("enrolledCount", 0) + 1
    await db.set_doc("workshops", workshop_id, workshop)
    return JSONResponse(status_code=201, content={"enrolled": True})


@router.get("/expert-talks")
async def list_talks(page: int = 1, pageSize: int = 20, uid: str = Depends(current_user_id)):
    talks = await db.query("expert_talks", [], limit=1000)
    talks.sort(key=lambda t: t.get("scheduledTime", ""))
    return _envelope(talks, page, _page_size(pageSize))


@router.post("/expert-talks/{talk_id}/register")
async def register_talk(talk_id: str, uid: str = Depends(current_user_id)):
    talk = await db.get_doc("expert_talks", talk_id)
    if talk is None:
        raise HTTPException(status_code=404, detail={"code": "TALK_NOT_FOUND", "message": "Talk not found", "fieldErrors": {}})
    reg_path = f"users/{uid}/talk_registrations"
    if await db.get_subdoc_at(reg_path, talk_id) is not None:
        raise HTTPException(status_code=409, detail={"code": "ALREADY_REGISTERED", "message": "पहले से पंजीकृत", "fieldErrors": {}})
    await db.set_subdoc_at(reg_path, talk_id, {"id": talk_id, "registeredAt": _now_iso()})
    talk["registeredCount"] = talk.get("registeredCount", 0) + 1
    await db.set_doc("expert_talks", talk_id, talk)
    coins_awarded = await coins_service.award_coins(uid, 25, "expert_talk", talk_id)
    return {"registered": True, "agriCoinsEarned": coins_awarded}


@router.post("/expert-talks/{talk_id}/questions", status_code=201)
async def ask_question(talk_id: str, body: QuestionIn, uid: str = Depends(current_user_id)):
    talk = await db.get_doc("expert_talks", talk_id)
    if talk is None:
        raise HTTPException(status_code=404, detail={"code": "TALK_NOT_FOUND", "message": "Talk not found", "fieldErrors": {}})
    question_id = uuid.uuid4().hex
    await db.set_subdoc_at(
        f"expert_talks/{talk_id}/questions",
        question_id,
        {"id": question_id, "userId": uid, "question": body.question, "askedAt": _now_iso()},
    )
    return {"asked": True}


@router.get("/videos")
async def list_videos(category: str | None = None, page: int = 1, pageSize: int = 20, uid: str = Depends(current_user_id)):
    videos = await db.query("videos", [], limit=1000)
    if category:
        videos = [v for v in videos if v.get("category") == category]
    return _envelope(videos, page, _page_size(pageSize))


@router.get("/blogs")
async def list_blogs(category: str | None = None, page: int = 1, pageSize: int = 20, uid: str = Depends(current_user_id)):
    blogs = await db.query("blogs", [], limit=1000)
    blogs.sort(key=lambda b: b.get("publishedDate", ""), reverse=True)
    bookmarks = {d["id"] for d in await db.list_subdocs(f"users/{uid}/bookmarks")}
    items = [{**b, "isBookmarked": b["id"] in bookmarks} for b in blogs]
    return _envelope(items, page, _page_size(pageSize))


@router.post("/blogs/{blog_id}/bookmark")
async def toggle_bookmark(blog_id: str, uid: str = Depends(current_user_id)):
    blog = await db.get_doc("blogs", blog_id)
    if blog is None:
        raise HTTPException(status_code=404, detail={"code": "BLOG_NOT_FOUND", "message": "Blog not found", "fieldErrors": {}})
    bookmark_path = f"users/{uid}/bookmarks"
    existing = await db.get_subdoc_at(bookmark_path, blog_id)
    if existing is not None:
        await db.delete_subdoc_at(bookmark_path, blog_id)
        return {"isBookmarked": False}
    await db.set_subdoc_at(bookmark_path, blog_id, {"id": blog_id, "bookmarkedAt": _now_iso()})
    return {"isBookmarked": True}


@router.post("/blogs/{blog_id}/like")
async def like_blog(blog_id: str, uid: str = Depends(current_user_id)):
    blog = await db.get_doc("blogs", blog_id)
    if blog is None:
        raise HTTPException(status_code=404, detail={"code": "BLOG_NOT_FOUND", "message": "Blog not found", "fieldErrors": {}})
    like_path = f"blogs/{blog_id}/likes"
    if await db.get_subdoc_at(like_path, uid) is None:
        await db.set_subdoc_at(like_path, uid, {"likedAt": _now_iso()})
        blog["likesCount"] = blog.get("likesCount", 0) + 1
        await db.set_doc("blogs", blog_id, blog)
    return {"likesCount": blog.get("likesCount", 0)}
