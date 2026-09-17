from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.core import db
from app.core.deps import current_user_id, require_profile
from app.models.finance import CreditScoreOut, KccOut, LoanApplyIn, LoanApplyOut, LoanCalcIn, LoanCalcOut
from app.services import users as users_service

router = APIRouter(prefix="/finance", tags=["finance"])

TIER_LIMITS = {"Bronze": 25000, "Silver": 50000, "Gold": 100000, "Platinum": 200000}


async def _user_or_403(uid: str, *roles) -> dict:
    user = await users_service.get_user(uid)
    require_profile(user, *roles)
    return user


@router.get("/credit-score")
async def credit_score(uid: str = Depends(current_user_id)):
    user = await _user_or_403(uid, "farmer", "farmLandlord", "transport", "seller", "equipmentRental", "broker")
    score = user.get("kisanCreditScore") or 650
    tier = user.get("creditTier") or "Silver"
    return CreditScoreOut(
        kisanCreditScore=score,
        creditTier=tier,
        creditLimit=TIER_LIMITS.get(tier, 50000),
        factors=["Timely KCC repayment", "Crop insurance coverage", "3-season income history"],
    )


@router.post("/loan-calculator")
async def loan_calculator(body: LoanCalcIn, uid: str = Depends(current_user_id)):
    await _user_or_403(uid, "farmer", "farmLandlord", "transport", "seller", "equipmentRental", "broker")
    r = body.interestRate / 12 / 100
    n = body.tenureMonths
    emi = round(body.amount * r * (1 + r) ** n / ((1 + r) ** n - 1), 2)
    total_payable = round(emi * n, 2)
    total_interest = round(total_payable - body.amount, 2)
    return LoanCalcOut(emi=emi, totalInterest=total_interest, totalPayable=total_payable)


@router.get("/kcc")
async def kcc(uid: str = Depends(current_user_id)):
    user = await _user_or_403(uid, "farmer")
    kcc_limit = user.get("kccLimit") or 0
    if not kcc_limit:
        raise HTTPException(
            status_code=404,
            detail={"code": "KCC_NOT_FOUND", "message": "No KCC linked for this user", "fieldErrors": {}},
        )
    phone = user.get("phone", "")
    return KccOut(
        bankName=user.get("bankName", ""),
        cardNumberMasked=f"XXXX-XXXX-{phone[-4:]}" if len(phone) >= 4 else "XXXX-XXXX-XXXX",
        kccLimit=kcc_limit,
        availableLimit=kcc_limit,
    )


@router.post("/loans/apply", status_code=201)
async def apply_loan(body: LoanApplyIn, uid: str = Depends(current_user_id)):
    await _user_or_403(uid, "farmer")
    application_id = uuid4().hex
    await db.set_doc(
        "loan_applications",
        application_id,
        {
            "id": application_id,
            "applicationId": application_id,
            **body.model_dump(),
            "userId": uid,
            "status": "submitted",
            "createdAt": datetime.now(timezone.utc).isoformat(),
        },
    )
    return LoanApplyOut(applicationId=application_id, status="submitted")


@router.get("/loans")
async def list_loans(page: int = 1, pageSize: int = 20, uid: str = Depends(current_user_id)):
    await _user_or_403(uid, "farmer")
    docs = await db.query("loan_applications", [("userId", "==", uid)], limit=1000)
    docs.sort(key=lambda d: d.get("createdAt", ""), reverse=True)
    total = len(docs)
    page_size = max(1, min(pageSize, 50))
    start = (max(1, page) - 1) * page_size
    data = [{**d, "applicationId": d.get("id") or d.get("applicationId")} for d in docs[start : start + page_size]]
    return {"data": data, "page": page, "pageSize": page_size, "total": total}
