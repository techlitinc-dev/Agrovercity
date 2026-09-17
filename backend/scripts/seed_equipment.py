import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.db import set_doc

EQUIPMENT = [
    {
        "id": "eq-1",
        "name": "Mahindra 575 DI Tractor",
        "type": "tractor",
        "ownerType": "fpo",
        "hourlyRate": 650,
        "perAcreRate": None,
        "distanceKm": 2.5,
        "ownerId": "sahyadri-fpo",
        "docStatus": "verified",
        "rejectionReason": None,
        "active": True,
    },
    {
        "id": "eq-2",
        "name": "Shaktiman Rotavator",
        "type": "rotavator",
        "ownerType": "private",
        "hourlyRate": 500,
        "perAcreRate": None,
        "distanceKm": 4.0,
        "ownerId": "owner-demo",
        "docStatus": "verified",
        "rejectionReason": None,
        "active": True,
    },
]


async def main():
    for doc in EQUIPMENT:
        await set_doc("equipment", doc["id"], doc)
    print(f"seeded {len(EQUIPMENT)} equipment")


if __name__ == "__main__":
    asyncio.run(main())
