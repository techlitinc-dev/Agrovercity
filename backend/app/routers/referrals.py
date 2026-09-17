from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.core import db
from app.core.deps import current_user_id
from app.services import coins as coins_service
from app.services import sms as sms_service
from app.services import users as users_service

router = APIRouter(prefix="/referrals", tags=["referrals"])

MILESTONES = [
    {"count": 1, "reward": "+100 coins"},
    {"count": 5, "reward": "Free soil test"},
    {"count": 10, "reward": "₹500 equipment discount"},
]


def _referrals_path(uid: str) -> str:
    return f"users/{uid}/referrals"


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


@router.get("")
async def get_referrals(uid: str = Depends(current_user_id)):
    user = await users_service.get_user(uid) or {}
    referral_code = user.get("referralCode")
    if not referral_code:
        name = (user.get("name") or "FARMER").replace(" ", "").upper()
        referral_code = f"{name}{datetime.now(timezone.utc).year}"
        user["referralCode"] = referral_code
        await users_service.save_user(uid, user)

    referred = await db.list_subdocs(_referrals_path(uid))
    milestones = [
        {**m, "achieved": len(referred) >= m["count"]}
        for m in MILESTONES
    ]
    return {"referralCode": referral_code, "milestones": milestones, "referred": referred}


@router.post("/invite", status_code=201)
async def invite(body: dict, uid: str = Depends(current_user_id)):
    farmer_name = body.get("farmerName", "")
    phone = body.get("phone", "")
    if not phone.startswith("+91") or len(phone) != 13:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "phone must be +91 followed by 10 digits", "fieldErrors": {"phone": "must be +91XXXXXXXXXX"}},
        )
    user = await users_service.get_user(uid) or {}
    referral_code = user.get("referralCode") or f"{(user.get('name') or 'FARMER').replace(' ', '').upper()}{datetime.now(timezone.utc).year}"

    existing = await db.list_subdocs(_referrals_path(uid))
    if any(r.get("phone") == phone for r in existing):
        raise HTTPException(status_code=409, detail={"code": "ALREADY_INVITED", "message": "पहले से आमंत्रित", "fieldErrors": {}})

    ref_id = f"ref_{uuid4().hex[:10]}"
    await db.set_subdoc_at(
        _referrals_path(uid),
        ref_id,
        {
            "id": ref_id,
            "farmerName": farmer_name,
            "phone": phone,
            "status": "Joined",
            "rewardCoins": 100,
            "joinDate": _today(),
        },
    )
    await sms_service.send_invite(phone, referral_code)
    awarded = await coins_service.award_coins(uid, 100, "referral", ref_id)
    return {"agriCoinsEarned": awarded}
