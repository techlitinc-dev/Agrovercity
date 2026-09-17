from app.core import db

FACILITIES = [
    {"id": "cs-1", "name": "Nashik Cold Storage Co-op", "distanceKm": 6.5, "tempRange": "2–8°C", "availableMT": 50, "ratePerQuintalMonth": 45, "bookedQuintals": 0},
    {"id": "cs-2", "name": "Pimpalgaon Cold Chain", "distanceKm": 14.0, "tempRange": "0–4°C", "availableMT": 120, "ratePerQuintalMonth": 38, "bookedQuintals": 0},
    {"id": "cs-3", "name": "Lasalgaon Mega Storage", "distanceKm": 28.0, "tempRange": "2–10°C", "availableMT": 300, "ratePerQuintalMonth": 32, "bookedQuintals": 0},
    {"id": "cs-4", "name": "Ozar Village Cold Room", "distanceKm": 3.2, "tempRange": "8–15°C", "availableMT": 20, "ratePerQuintalMonth": 55, "bookedQuintals": 0},
]


async def seed_cold_storage():
    if await db.query("cold_storage", [], limit=1):
        return
    for doc in FACILITIES:
        await db.set_doc("cold_storage", doc["id"], doc)
