import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.db import set_doc

PRODUCTS = [
    {
        "id": "prod-1",
        "title": "Tomato Seeds Hybrid (टमाटर बीज)",
        "vernacularTitle": "टमाटर बीज हायब्रिड",
        "category": "seeds",
        "brand": "Sungro",
        "rating": 4.3,
        "reviewsCount": 128,
        "dealerName": "Kisan Agro Seva Kendra",
        "distanceKm": 6.2,
        "mrp": 450,
        "discountedPrice": 380,
        "bnplAvailable": True,
        "batchNo": "BATCH-TS-1042",
    },
    {
        "id": "prod-2",
        "title": "Urea 45kg (यूरिया)",
        "vernacularTitle": "यूरिया 45 किलो",
        "category": "fertilizer",
        "brand": "IFFCO",
        "rating": 4.5,
        "reviewsCount": 342,
        "dealerName": "Nashik Fertilizers Traders",
        "distanceKm": 12.0,
        "mrp": 280,
        "discountedPrice": 266,
        "bnplAvailable": False,
        "batchNo": "BATCH-UR-2201",
    },
    {
        "id": "prod-3",
        "title": "Chlorpyrifos Pesticide (कीटनाशक)",
        "vernacularTitle": "क्लोरपायरीफॉस कीटनाशक",
        "category": "pesticide",
        "brand": "Dhanuka",
        "rating": 4.1,
        "reviewsCount": 87,
        "dealerName": "Kisan Agro Seva Kendra",
        "distanceKm": 6.2,
        "mrp": 560,
        "discountedPrice": 499,
        "bnplAvailable": True,
        "batchNo": "BATCH-CP-3305",
    },
]


def _certificate(batch_no: str) -> dict:
    return {
        "batchNo": batch_no,
        "certifier": "AGMARK / Ministry of Agriculture",
        "certificateNo": f"AGM-2026-{batch_no.split('-')[-1]}",
        "valid": True,
        "verifiedAt": datetime.now(timezone.utc).isoformat(),
    }


CERTIFICATES = [_certificate(p["batchNo"]) for p in PRODUCTS]


async def main():
    for doc in PRODUCTS:
        await set_doc("products", doc["id"], doc)
    for doc in CERTIFICATES:
        await set_doc("certificates", doc["batchNo"], doc)
    print(f"seeded {len(PRODUCTS)} products, {len(CERTIFICATES)} certificates")


if __name__ == "__main__":
    asyncio.run(main())
