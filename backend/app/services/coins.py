from datetime import datetime, timezone
from uuid import uuid4

from app.core import db


async def award_coins(uid: str, amount: int, reason: str, ref_id: str | None = None) -> int:
    user = await db.get_doc("users", uid)
    balance = (user or {}).get("agriCoins", 0) + amount
    if user is not None:
        user["agriCoins"] = balance
        await db.set_doc("users", uid, user)
    await db.set_subdoc_at(
        f"users/{uid}/coin_ledger",
        str(uuid4()),
        {"id": str(uuid4()), "amount": +amount, "reason": reason, "refId": ref_id, "at": datetime.now(timezone.utc).isoformat()},
    )
    return balance
