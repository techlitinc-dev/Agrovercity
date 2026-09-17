from datetime import date, timedelta

from app.core import db


SCHEMES = [
    {
        "id": "pm-kisan",
        "name": "PM-KISAN",
        "category": "income-support",
        "benefitAmount": "₹6,000/वर्ष",
        "documentsRequired": ["Aadhaar", "7/12", "Bank passbook"],
        "status": "open",
        "nextDeadline": (date.today() + timedelta(days=45)).isoformat(),
        "description": "केंद्र सरकार की आय सहायता योजना — हर किसान परिवार को ₹6,000 प्रति वर्ष।",
        "eligibilityRules": {"maxLandAcres": 10, "states": [], "requiresKcc": False},
    },
    {
        "id": "pmfby",
        "name": "PMFBY (फसल बीमा)",
        "category": "insurance",
        "benefitAmount": "फसल हानि पर पूर्ण क्षतिपूर्ति",
        "documentsRequired": ["Aadhaar", "7/12", "Bank passbook", "Sowing certificate"],
        "status": "open",
        "nextDeadline": (date.today() + timedelta(days=30)).isoformat(),
        "description": "प्रधानमंत्री फसल बीमा योजना — प्राकृतिक आपदा से फसल हानि पर बीमा कवर।",
        "eligibilityRules": {"states": []},
    },
    {
        "id": "soil-health-card",
        "name": "Soil Health Card",
        "category": "soil",
        "benefitAmount": "निःशुल्क मिट्टी परीक्षण",
        "documentsRequired": ["Aadhaar", "7/12"],
        "status": "open",
        "nextDeadline": (date.today() + timedelta(days=60)).isoformat(),
        "description": "मिट्टी के स्वास्थ्य की जांच और पोषक तत्वों की सिफारिश — निःशुल्क।",
        "eligibilityRules": {},
    },
    {
        "id": "pm-kusum",
        "name": "PM-KUSUM (सोलर पंप)",
        "category": "solar",
        "benefitAmount": "सोलर पंप पर 60% सब्सिडी",
        "documentsRequired": ["Aadhaar", "7/12", "Bank passbook", "Electricity connection"],
        "status": "open",
        "nextDeadline": (date.today() + timedelta(days=90)).isoformat(),
        "description": "सोलर उर्जा से सिंचाई पंप — बिजली बिल से मुक्ति और 60% सब्सिडी।",
        "eligibilityRules": {"maxLandAcres": 5},
    },
    {
        "id": "enam",
        "name": "eNAM",
        "category": "market",
        "benefitAmount": "ऑनलाइन मंडी एक्सेस",
        "documentsRequired": ["Aadhaar", "Bank passbook"],
        "status": "open",
        "nextDeadline": (date.today() + timedelta(days=120)).isoformat(),
        "description": "इलेक्ट्रॉनिक नेशनल एग्रीकल्चर मार्केट — देशभर की मंडियों से ऑनलाइन जुड़ाव।",
        "eligibilityRules": {},
    },
    {
        "id": "pmksy-drip",
        "name": "PMKSY ड्रिप सब्सिडी",
        "category": "irrigation",
        "benefitAmount": "ड्रिप सिंचाई पर 55% सब्सिडी",
        "documentsRequired": ["Aadhaar", "7/12", "Bank passbook", "Land irrigation proof"],
        "status": "open",
        "nextDeadline": (date.today() + timedelta(days=75)).isoformat(),
        "description": "प्रधानमंत्री कृषि सिंचाई योजना — ड्रिप/स्प्रिंकलर पर 55% सब्सिडी।",
        "eligibilityRules": {"maxLandAcres": 8, "states": ["Maharashtra", "Gujarat", "Madhya Pradesh"]},
    },
]


async def seed_schemes():
    existing = await db.query("schemes", [], limit=1)
    if existing:
        return
    for doc in SCHEMES:
        await db.set_doc("schemes", doc["id"], doc)
