from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core import db

LEVEL_THRESHOLDS = [0, 500, 1500, 3000, 6000]
LEVEL_TITLES = ["Krishi Yuva", "Krishi Daksh", "Krishi Praveen", "Krishi Ratna", "Krishi Samrat"]
DAILY_EARN_CAP = 200
DAILY_REDEEM_LIMIT = 1


class InsufficientCoins(Exception):
    pass


def _ledger_path(uid: str) -> str:
    return f"users/{uid}/coin_ledger"


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _level_for(balance: int) -> int:
    level = 1
    for i, threshold in enumerate(LEVEL_THRESHOLDS):
        if balance >= threshold:
            level = i + 1
    return level


def _apply_level_and_streak(user: dict, ledger: list[dict]):
    balance = user.get("agriCoins", 0)
    user["krishiRatnaLevel"] = _level_for(balance)
    user["krishiRatnaTitle"] = LEVEL_TITLES[user["krishiRatnaLevel"] - 1]

    today = _today()
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
    dates = sorted({e.get("at", "")[:10] for e in ledger}, reverse=True)
    if not dates:
        user["streakDays"] = 1
    elif dates[0] != today:
        user["streakDays"] = 1
    elif len(dates) > 1 and dates[1] == yesterday:
        user["streakDays"] = user.get("streakDays", 0) + 1
    # dates[0] == today and previous != yesterday → unchanged


async def award_coins(uid: str, amount: int, reason: str, ref_id: str | None = None) -> int:
    """Awards coins with the daily earn cap; returns the actually-awarded amount."""
    ledger = await db.list_subdocs(_ledger_path(uid))
    earned_today = sum(e.get("amount", 0) for e in ledger if e.get("at", "").startswith(_today()) and e.get("amount", 0) > 0)
    awarded = min(amount, max(0, DAILY_EARN_CAP - earned_today))
    entry_reason = reason if awarded > 0 else f"{reason}_capped"

    entry_id = str(uuid4())
    await db.set_subdoc_at(
        _ledger_path(uid),
        entry_id,
        {"id": entry_id, "amount": awarded, "reason": entry_reason, "refId": ref_id, "at": datetime.now(timezone.utc).isoformat()},
    )

    if awarded > 0:
        user = await db.get_doc("users", uid)
        if user is not None:
            user["agriCoins"] = user.get("agriCoins", 0) + awarded
            _apply_level_and_streak(user, await db.list_subdocs(_ledger_path(uid)))
            await db.set_doc("users", uid, user)
    return awarded


async def spend_coins(uid: str, amount: int, reason: str, ref_id: str | None = None) -> int:
    user = await db.get_doc("users", uid)
    balance = (user or {}).get("agriCoins", 0)
    if balance < amount:
        raise InsufficientCoins(f"Balance {balance} < {amount}")
    new_balance = balance - amount
    if user is not None:
        user["agriCoins"] = new_balance
        await db.set_doc("users", uid, user)
    await db.set_subdoc_at(
        _ledger_path(uid),
        str(uuid4()),
        {"id": str(uuid4()), "amount": -amount, "reason": reason, "refId": ref_id, "at": datetime.now(timezone.utc).isoformat()},
    )
    return new_balance
