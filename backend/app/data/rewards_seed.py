from app.core import db

REWARDS = [
    {"id": "reward-iffco", "title": "₹200 IFFCO voucher", "coinCost": 300, "type": "voucher"},
    {"id": "reward-soil-test", "title": "Free soil test", "coinCost": 500, "type": "service"},
    {"id": "reward-video-call", "title": "1-on-1 scientist video call", "coinCost": 800, "type": "service"},
]


async def seed_rewards():
    if await db.query("rewards", [], limit=1):
        return
    for doc in REWARDS:
        await db.set_doc("rewards", doc["id"], doc)
