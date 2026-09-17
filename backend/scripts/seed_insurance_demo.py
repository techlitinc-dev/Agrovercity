import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.db import get_subdoc_at, list_subdocs, set_subdoc_at

DEMO_POLICY = {
    "id": "policy-demo",
    "policyNumber": "PMFBY-2026-0001",
    "schemeName": "PMFBY",
    "cropName": "Wheat",
    "season": "Kharif",
    "year": 2026,
    "landAreaAcres": 2.0,
    "sumInsured": 80000,
    "farmerPremium": 1600,
    "govtSubsidy": 8400,
    "status": "active",
    "insuranceCompany": "AIC of India",
    "coverageStartDate": "2026-07-01",
    "coverageEndDate": "2026-12-31",
    "bankName": "SBI",
    "kccAccountNo": "XXXX4521",
    "certificateUrl": None,
    "createdAt": datetime.now(timezone.utc).isoformat(),
}


def _claim(number: str, status: str, timeline: list[dict], approved_amount=None, dbt_id=None) -> dict:
    surveyor = {"surveyorName": "संदीप कुल्कर्णी", "surveyorPhone": "+919811000001", "surveyorVisitDate": (datetime.now(timezone.utc) + timedelta(days=3)).date().isoformat()}
    return {
        "id": number.lower().replace("-", "_"),
        "claimNumber": number,
        "policyId": "policy-demo",
        "cropName": "Wheat",
        "calamityType": "hailstorm",
        "dateOfDamage": "2026-09-10",
        "cropStage": "flowering",
        "estimatedLossPercent": 40,
        "requestedAmount": 32000,
        "approvedAmount": approved_amount,
        "status": status,
        "statusText": "सर्वेयर नियुक्त" if status == "surveyorAssigned" else "राशि वितरित",
        "surveyorName": surveyor["surveyorName"],
        "surveyorPhone": surveyor["surveyorPhone"],
        "surveyorVisitDate": surveyor["surveyorVisitDate"],
        "gpsCoordinates": "20.0,73.8",
        "village": "Ozarkhed",
        "damagePhotos": [],
        "submittedAt": datetime.now(timezone.utc).isoformat(),
        "dbtTransactionId": dbt_id,
        "bankAccountLast4": "4521",
        "timeline": timeline,
        "appealCount": 0,
        "rejectionReason": None,
    }


async def main(uid: str):
    claims_path = f"users/{uid}/insurance_claims"
    existing = await list_subdocs(claims_path)
    if existing:
        print(f"skipped — demo insurance already seeded for {uid}")
        return
    if await get_subdoc_at(f"users/{uid}/insurance_policies", "policy-demo") is None:
        await set_subdoc_at(f"users/{uid}/insurance_policies", "policy-demo", DEMO_POLICY)

    now = datetime.now(timezone.utc).isoformat()
    claim1 = _claim(
        "CLM-2026-MH-9001",
        "surveyorAssigned",
        [
            {"status": "intimated", "at": now, "note": "Claim intimated within 72h window"},
            {"status": "surveyorAssigned", "at": now, "note": "Surveyor assigned"},
        ],
    )
    claim2 = _claim(
        "CLM-2026-MH-9002",
        "disbursed",
        [
            {"status": "intimated", "at": now, "note": "Claim intimated within 72h window"},
            {"status": "surveyorAssigned", "at": now, "note": "Surveyor assigned"},
            {"status": "fieldAssessed", "at": now, "note": "Field assessment complete"},
            {"status": "dbtApproved", "at": now, "note": "DBT approved"},
            {"status": "disbursed", "at": now, "note": "Amount disbursed"},
        ],
        approved_amount=22400,
        dbt_id="DBT20260901234",
    )
    await set_subdoc_at(claims_path, claim1["id"], claim1)
    await set_subdoc_at(claims_path, claim2["id"], claim2)
    print(f"seeded demo insurance for {uid}")


if __name__ == "__main__":
    uid = sys.argv[1] if len(sys.argv) > 1 else "uid-1"
    asyncio.run(main(uid))
