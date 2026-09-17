from app.core import db

RATES = [
    {"id": "rate-wheat-kharif", "cropName": "Wheat", "category": "kharif-crops", "season": "Kharif", "sumInsuredPerAcre": 40000, "farmerSharePercent": 2.0, "totalActuarialRatePercent": 12.5, "cutoffDate": "2026-07-31"},
    {"id": "rate-onion-kharif", "cropName": "Onion", "category": "kharif-crops", "season": "Kharif", "sumInsuredPerAcre": 35000, "farmerSharePercent": 2.0, "totalActuarialRatePercent": 11.0, "cutoffDate": "2026-07-31"},
    {"id": "rate-soybean-kharif", "cropName": "Soybean", "category": "kharif-crops", "season": "Kharif", "sumInsuredPerAcre": 30000, "farmerSharePercent": 2.0, "totalActuarialRatePercent": 10.0, "cutoffDate": "2026-07-31"},
    {"id": "rate-wheat-rabi", "cropName": "Wheat", "category": "rabi-crops", "season": "Rabi", "sumInsuredPerAcre": 38000, "farmerSharePercent": 1.5, "totalActuarialRatePercent": 9.5, "cutoffDate": "2026-12-15"},
    {"id": "rate-gram-rabi", "cropName": "Gram", "category": "rabi-crops", "season": "Rabi", "sumInsuredPerAcre": 32000, "farmerSharePercent": 1.5, "totalActuarialRatePercent": 9.0, "cutoffDate": "2026-12-15"},
    {"id": "rate-sugarcane-annual", "cropName": "Sugarcane", "category": "annual", "season": "Annual", "sumInsuredPerAcre": 90000, "farmerSharePercent": 5.0, "totalActuarialRatePercent": 14.0, "cutoffDate": "2026-12-31"},
]


async def seed_insurance_rates():
    existing = await db.query("insurance_rates", [], limit=1)
    if existing:
        return
    for doc in RATES:
        await db.set_doc("insurance_rates", doc["id"], doc)
