import math

from fastapi import APIRouter, Depends, HTTPException

from app.core import db
from app.core.deps import current_user_id, require_profile
from app.models.pnl import BreakEvenIn, BreakEvenOut, CropPandL, ExpenseIn, PnlSummary
from app.data.demo_pnl import DEMO_CROPS
from app.services import users as users_service

router = APIRouter(prefix="/pnl", tags=["pnl"])

ROLES = ("farmer", "farmLandlord", "seller", "equipmentRental", "broker")


def _crops_path(uid: str) -> str:
    return f"users/{uid}/crop_pnl"


async def _user_or_403(uid: str) -> dict:
    user = await users_service.get_user(uid)
    require_profile(user, *ROLES)
    return user


@router.get("/summary")
async def summary(uid: str = Depends(current_user_id)):
    await _user_or_403(uid)
    crops = await db.list_subdocs(_crops_path(uid))
    gross = sum(c.get("grossRevenue", 0) for c in crops)
    cost = sum(c.get("totalExpenses", 0) for c in crops)
    return PnlSummary(grossIncome=gross, productionCost=cost, netProfit=gross - cost)


@router.get("/crops")
async def list_crops(page: int = 1, pageSize: int = 20, uid: str = Depends(current_user_id)):
    await _user_or_403(uid)
    crops = await db.list_subdocs(_crops_path(uid))
    if not crops:
        for crop in DEMO_CROPS:
            await db.set_subdoc_at(_crops_path(uid), crop["id"], crop)
        crops = await db.list_subdocs(_crops_path(uid))
    total = len(crops)
    page_size = max(1, min(pageSize, 50))
    start = (max(1, page) - 1) * page_size
    return {"data": crops[start : start + page_size], "page": page, "pageSize": page_size, "total": total}


@router.post("/crops/{crop_id}/expenses")
async def add_expense(crop_id: str, body: ExpenseIn, uid: str = Depends(current_user_id)):
    await _user_or_403(uid)
    crop = await db.get_subdoc_at(_crops_path(uid), crop_id)
    if crop is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "CROP_NOT_FOUND", "message": "Crop not found", "fieldErrors": {}},
        )
    breakdown = list(crop.get("expensesBreakdown", []))
    breakdown.append({"category": body.category, "amount": body.amount})
    crop["expensesBreakdown"] = breakdown
    total_expenses = sum(b["amount"] for b in breakdown)
    crop["totalExpenses"] = total_expenses
    crop["netProfit"] = crop.get("grossRevenue", 0) - total_expenses
    crop["roiPercent"] = round(crop["netProfit"] / total_expenses * 100, 1) if total_expenses else 0
    await db.set_subdoc_at(_crops_path(uid), crop_id, crop)
    return CropPandL(**crop)


@router.post("/break-even")
async def break_even(body: BreakEvenIn, uid: str = Depends(current_user_id)):
    await _user_or_403(uid)
    return BreakEvenOut(minSafePricePerQuintal=math.ceil(body.totalCost / body.expectedYieldQuintals))
