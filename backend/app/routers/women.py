from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core import db
from app.core.deps import require_roles

router = APIRouter(prefix="/women", tags=["women"])

ROLE = ("farmer",)

SHG_DEFAULTS = {"memberCount": 12, "corpus": 48500, "loanFund": 30000, "monthlyDeposit": 500}

ENTERPRISE_LINES = [
    {"product": "अचार", "monthlyProfit": 3200},
    {"product": "पापड़", "monthlyProfit": 2100},
    {"product": "A2 घी", "monthlyProfit": 4500},
]


class DepositIn(BaseModel):
    amount: float = Field(gt=0)
    month: str = Field(pattern=r"^\d{4}-\d{2}$")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/shg")
async def get_shg(user: dict = Depends(require_roles(*ROLE))):
    uid = user["id"]
    profile = await db.get_subdoc_at(f"users/{uid}/shg", "profile")
    if profile is None:
        profile = {"id": "profile", **SHG_DEFAULTS, "updatedAt": _now_iso()}
        await db.set_subdoc_at(f"users/{uid}/shg", "profile", profile)
    return profile


@router.post("/shg/deposit", status_code=201)
async def deposit(body: DepositIn, user: dict = Depends(require_roles(*ROLE))):
    uid = user["id"]
    profile = await db.get_subdoc_at(f"users/{uid}/shg", "profile")
    if profile is None:
        profile = {"id": "profile", **SHG_DEFAULTS, "updatedAt": _now_iso()}
        await db.set_subdoc_at(f"users/{uid}/shg", "profile", profile)

    deposits = await db.list_subdocs(f"users/{uid}/shg/deposits")
    if any(d.get("month") == body.month for d in deposits):
        raise HTTPException(
            status_code=409,
            detail={"code": "DUPLICATE_DEPOSIT_MONTH", "message": "इस महीने की जमा हो चुकी है", "fieldErrors": {}},
        )
    deposit_id = uuid4().hex
    await db.set_subdoc_at(
        f"users/{uid}/shg/deposits",
        deposit_id,
        {"id": deposit_id, "amount": body.amount, "month": body.month, "depositedAt": _now_iso()},
    )
    profile["corpus"] = profile.get("corpus", 0) + body.amount
    await db.set_subdoc_at(f"users/{uid}/shg", "profile", profile)
    return {"deposited": body.amount, "newCorpus": profile["corpus"]}


@router.get("/home-enterprise")
async def home_enterprise(user: dict = Depends(require_roles(*ROLE))):
    uid = user["id"]
    summary = await db.get_subdoc_at(f"users/{uid}/home_enterprise", "summary")
    if summary is None:
        summary = {"id": "summary", "lines": ENTERPRISE_LINES}
        await db.set_subdoc_at(f"users/{uid}/home_enterprise", "summary", summary)
    total = sum(line.get("monthlyProfit", 0) for line in summary.get("lines", []))
    return {"lines": summary.get("lines", []), "totalMonthlyProfit": total}
