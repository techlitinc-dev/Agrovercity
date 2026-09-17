import zlib
from datetime import date, datetime, timedelta, timezone

from app.core import db
from app.services import fcm as fcm_service

CLAIM_TRANSITIONS = {
    "intimated": ["surveyorAssigned"],
    "surveyorAssigned": ["fieldAssessed"],
    "fieldAssessed": ["dbtApproved", "rejected"],
    "dbtApproved": ["disbursed"],
    "disbursed": [],
    "rejected": [],
}

STATUS_TEXT = {
    "intimated": "दावा दर्ज — सर्वेयर नियुक्ति लंबित",
    "surveyorAssigned": "सर्वेयर नियुक्त",
    "fieldAssessed": "क्षेत्र मूल्यांकन पूर्ण",
    "dbtApproved": "DBT स्वीकृत",
    "disbursed": "राशि वितरित",
    "rejected": "दावा अस्वीकृत",
}

STATE_CODES = {
    "Maharashtra": "MH",
    "Madhya Pradesh": "MP",
    "Gujarat": "GJ",
    "Uttar Pradesh": "UP",
    "Punjab": "PB",
    "Rajasthan": "RJ",
}

SURVEYOR_POOL = [
    ("संदीप कुलकर्णी", "+919811000001"),
    ("मीना जाधव", "+919811000002"),
    ("अजय भोसले", "+919811000003"),
]


async def advance_status(claim: dict, new_status: str, note: str = "", uid: str | None = None) -> dict:
    if new_status not in CLAIM_TRANSITIONS.get(claim.get("status"), []):
        raise ValueError(f"Illegal transition from {claim.get('status')} to {new_status}")
    claim["status"] = new_status
    claim["statusText"] = STATUS_TEXT[new_status]
    claim.setdefault("timeline", []).append(
        {"status": new_status, "at": datetime.now(timezone.utc).isoformat(), "note": note}
    )
    if uid:
        await fcm_service.notify(
            uid,
            f"दावा अपडेट: {claim.get('claimNumber', '')}",
            STATUS_TEXT[new_status],
            {"type": "claim", "claimId": claim.get("id", "")},
        )
    return claim


def state_code(state: str | None) -> str:
    return STATE_CODES.get(state or "", "XX")


async def next_claim_number(state_code_str: str) -> str:
    year = datetime.now(timezone.utc).year
    counter_id = f"claims_{year}"
    counter = await db.get_doc("counters", counter_id)
    count = (counter or {}).get("count", 0) + 1
    await db.set_doc("counters", counter_id, {"count": count})
    return f"CLM-{year}-{state_code_str}-{count:04d}"


def auto_assign_surveyor(district: str) -> dict:
    name, phone = SURVEYOR_POOL[zlib.crc32(district.encode()) % 3]
    return {
        "surveyorName": name,
        "surveyorPhone": phone,
        "surveyorVisitDate": (date.today() + timedelta(days=3)).isoformat(),
    }


async def appeal(claim: dict, reason: str, uid: str | None = None) -> dict:
    if claim.get("status") != "rejected":
        raise ValueError(f"Cannot appeal a claim in status {claim.get('status')}")
    claim["status"] = "intimated"
    claim["statusText"] = STATUS_TEXT["intimated"]
    claim["appealCount"] = claim.get("appealCount", 0) + 1
    claim.setdefault("timeline", []).append(
        {
            "status": "intimated",
            "at": datetime.now(timezone.utc).isoformat(),
            "note": f"Appeal submitted: {reason[:100]}",
        }
    )
    if uid:
        await fcm_service.notify(
            uid,
            f"दावा अपडेट: {claim.get('claimNumber', '')}",
            STATUS_TEXT["intimated"],
            {"type": "claim", "claimId": claim.get("id", "")},
        )
    return claim
