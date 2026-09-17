import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.db import set_doc

# flutter-prototype/ is absent from this repo — the day-file asked for the 3
# dummyBuyerContracts values copied exactly from demo_data.dart. Values below are
# realistic stand-ins consistent with the ContractOut model; diff if the prototype appears.
CONTRACTS = [
    {
        "id": "contract-1",
        "buyerCompany": "Mahagrapes Exports Pvt Ltd",
        "buyerRating": 4.6,
        "crop": "Tomato",
        "lockedRateQuintal": 2450,
        "mspCurrentRate": 2100,
        "premiumAboveMSP": 16.7,
        "minQuantityQuintals": 50,
        "deliveryLocation": "Pimpalgaon APMC Yard, Nashik",
        "paymentTerms": "50% advance, 50% on delivery",
        "status": "open",
        "contractDuration": "6 months",
        "termsText": "यह अनुबंध कीमत लॉक करता है: ₹2450/क्विंटल टमाटर। न्यूनतम 50 क्विंटल आपूर्ति अनिवार्य है। This agreement locks the rate for the stated crop and quantity; delivery at the stated APMC yard as per schedule.",
    },
    {
        "id": "contract-2",
        "buyerCompany": "Nashik Food Processing Park",
        "buyerRating": 4.3,
        "crop": "Onion",
        "lockedRateQuintal": 2280,
        "mspCurrentRate": 1750,
        "premiumAboveMSP": 30.3,
        "minQuantityQuintals": 100,
        "deliveryLocation": "Lasalgaon APMC Yard, Nashik",
        "paymentTerms": "100% payment within 7 days of delivery",
        "status": "open",
        "contractDuration": "4 months",
        "termsText": "यह अनुबंध प्याज की खरीद की शर्तें तय करता है: ₹2280/क्विंटल। भुगतान डिलीवरी के 7 दिनों में पूर्ण। Quality norms per APMC grading apply at delivery.",
    },
    {
        "id": "contract-3",
        "buyerCompany": "Safal Market (NDDB)",
        "buyerRating": 4.8,
        "crop": "Wheat",
        "lockedRateQuintal": 2400,
        "mspCurrentRate": 2275,
        "premiumAboveMSP": 5.5,
        "minQuantityQuintals": 200,
        "deliveryLocation": "Safal Collection Centre, Indore",
        "paymentTerms": "50% advance, 50% on delivery",
        "status": "open",
        "contractDuration": "12 months",
        "termsText": "यह अनुबंध गेहूं की खरीद की शर्तें तय करता है: ₹2400/क्विंटल। नमूना जांच के बाद ही स्वीकृति। Moisture and quality checks apply at the collection centre.",
    },
]


async def main():
    for doc in CONTRACTS:
        await set_doc("contracts", doc["id"], doc)
    print(f"seeded {len(CONTRACTS)} contracts")


if __name__ == "__main__":
    asyncio.run(main())
