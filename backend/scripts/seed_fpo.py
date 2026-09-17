import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.db import set_doc

FPO = {"id": "sahyadri-fpo", "name": "Sahyadri Shetkari FPO", "memberCount": 214, "district": "Nashik"}

POOL = {
    "id": "pool-1",
    "item": "Nano Urea (500 ml)",
    "bookedUnits": 380,
    "targetUnits": 500,
    "discountPercent": 18,
    "deadline": (datetime.now(timezone.utc) + timedelta(days=10)).date().isoformat(),
}


async def main():
    await set_doc("fpos", FPO["id"], FPO)
    await set_doc("fpo_pools", POOL["id"], POOL)
    print("seeded 1 fpo, 1 pool")


if __name__ == "__main__":
    asyncio.run(main())
