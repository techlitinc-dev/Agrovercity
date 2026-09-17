import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.core import db
from app.core.deps import require_roles
from app.models.mandi import SellerRateRequest

router = APIRouter(prefix="/seller", tags=["seller"])

# vyapari_rates:* Redis keys are invalidated only when a rate flips to approved —
# the approval flow is out of scope today (admin moderation queue, Day 14 A6).


def _find_reference(docs: list[dict], crop: str, mandi_name: str) -> dict | None:
    crop_docs = [d for d in docs if crop.lower() in d.get("commodity", "").lower()]
    for d in crop_docs:
        doc_name = d.get("mandiName", "").lower()
        if mandi_name.lower() in doc_name or doc_name in mandi_name.lower():
            return d
    return crop_docs[0] if crop_docs else None


@router.post("/rates")
async def post_rate(body: SellerRateRequest, user: dict = Depends(require_roles("seller"))):
    rate_per_quintal = body.ratePerKg * 100
    docs = await db.query("mandi_prices", [], limit=1000)
    reference = _find_reference(docs, body.crop, body.mandiName)
    if reference is not None and abs(rate_per_quintal - reference["modalPrice"]) > 0.25 * reference["modalPrice"]:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "RATE_OUT_OF_BAND",
                "message": "Rate is outside the ±25% band around the mandi modal price",
                "fieldErrors": {"ratePerKg": f"मंडी भाव ₹{reference['modalPrice']} के ±25% सीमा से बाहर"},
            },
        )
    rate_id = f"rate_{uuid4().hex[:10]}"
    doc = {
        "id": rate_id,
        "crop": body.crop,
        "ratePerKg": body.ratePerKg,
        "mandiName": body.mandiName,
        "sellerId": user["id"],
        "status": "pending",
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    await db.set_doc("vyapari_rates_pending", rate_id, doc)
    return doc


@router.get("/rates/my")
async def my_rates(user: dict = Depends(require_roles("seller"))):
    docs = await db.query("vyapari_rates_pending", [("sellerId", "==", user["id"])], limit=1000)
    return {"data": docs}
