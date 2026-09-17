from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.core import db
from app.core.deps import current_user_id
from app.models.gamification import GamificationStatus
from app.services import coins as coins_service
from app.services import users as users_service

router = APIRouter(prefix="/gamification", tags=["gamification"])

MAX_LEVEL = len(coins_service.LEVEL_THRESHOLDS)


@router.get("/status")
async def status(uid: str = Depends(current_user_id)):
    user = await db.get_doc("users", uid) or {}
    balance = user.get("agriCoins", 0)
    level = user.get("krishiRatnaLevel") or coins_service._level_for(balance)
    xp_to_next = 0
    if level < MAX_LEVEL:
        xp_to_next = coins_service.LEVEL_THRESHOLDS[level] - balance
    return GamificationStatus(
        krishiRatnaLevel=level,
        krishiRatnaTitle=user.get("krishiRatnaTitle") or "Krishi Yuva",
        agriCoins=balance,
        streakDays=user.get("streakDays", 0),
        xpToNextLevel=max(0, xp_to_next),
    )


@router.get("/rewards")
async def rewards(page: int = 1, pageSize: int = 20, uid: str = Depends(current_user_id)):
    docs = await db.query("rewards", [], limit=1000)
    total = len(docs)
    page_size = max(1, min(pageSize, 50))
    start = (max(1, page) - 1) * page_size
    return {"data": docs[start : start + page_size], "page": page, "pageSize": page_size, "total": total}


@router.post("/redeem")
async def redeem(body: dict, uid: str = Depends(current_user_id)):
    reward = await db.get_doc("rewards", body.get("rewardId", ""))
    if reward is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "REWARD_NOT_FOUND", "message": "Reward not found", "fieldErrors": {}},
        )
    ledger = await db.list_subdocs(f"users/{uid}/coin_ledger")
    redeemed_today = sum(1 for e in ledger if e.get("reason") == "redeem" and e.get("at", "").startswith(coins_service._today()))
    if redeemed_today >= coins_service.DAILY_REDEEM_LIMIT:
        raise HTTPException(
            status_code=409,
            detail={"code": "REDEMPTION_LIMIT_REACHED", "message": "आज की रिडीम सीमा पूरी — कल फिर कोशिश करें", "fieldErrors": {}},
        )
    try:
        new_balance = await coins_service.spend_coins(uid, reward["coinCost"], "redeem", reward["id"])
    except coins_service.InsufficientCoins:
        raise HTTPException(
            status_code=409,
            detail={"code": "INSUFFICIENT_COINS", "message": "पर्याप्त कॉइन नहीं", "fieldErrors": {}},
        )
    coupon_code = "KC-" + uuid4().hex[:8].upper() if reward.get("type") == "voucher" else None
    return {"newBalance": new_balance, "couponCode": coupon_code}


@router.get("/ledger")
async def ledger(page: int = 1, pageSize: int = 20, uid: str = Depends(current_user_id)):
    entries = await db.list_subdocs(f"users/{uid}/coin_ledger")
    entries.sort(key=lambda e: e.get("at", ""), reverse=True)
    total = len(entries)
    page_size = max(1, min(pageSize, 50))
    start = (max(1, page) - 1) * page_size
    return {"data": entries[start : start + page_size], "page": page, "pageSize": page_size, "total": total}
