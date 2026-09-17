from datetime import datetime, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core import db
from app.core.deps import require_roles
from app.models.claims import AppealIn
from app.services import claims as claims_service
from app.services import reports as reports_service
from app.services import storage as storage_service

router = APIRouter(prefix="/insurance", tags=["insurance"])

ROLES = ("farmer", "farmLandlord")

PHOTO_GUIDELINES = [
    "पूरे खेत की एक चौड़ी फोटो लें",
    "नुकसान वाले पौधों की नज़दीक से फोटो लें",
    "GPS चालू रखें — लोकेशन अपने आप जुड़ती है",
]

COVERAGE_WINDOWS = {
    "Kharif": ("{year}-07-01", "{year}-12-31"),
    "Rabi": ("{year}-10-01", "{next_year}-03-31"),
    "Annual": ("{year}-01-01", "{year}-12-31"),
}


def _policies_path(uid: str) -> str:
    return f"users/{uid}/insurance_policies"


def _claims_path(uid: str) -> str:
    return f"users/{uid}/insurance_claims"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/policies")
async def list_policies(page: int = 1, pageSize: int = 20, user: dict = Depends(require_roles(*ROLES))):
    uid = user["id"]
    policies = await db.list_subdocs(_policies_path(uid))
    if not policies:
        demo = {
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
            "createdAt": _now_iso(),
        }
        await db.set_subdoc_at(_policies_path(uid), demo["id"], demo)
        policies = [demo]
    total = len(policies)
    page_size = max(1, min(pageSize, 50))
    start = (max(1, page) - 1) * page_size
    return {"data": policies[start : start + page_size], "page": page, "pageSize": page_size, "total": total}


@router.post("/policies/apply", status_code=201)
async def apply_policy(body: dict, user: dict = Depends(require_roles(*ROLES))):
    uid = user["id"]
    rates = await db.query(
        "insurance_rates",
        [("cropName", "==", body.get("cropName")), ("season", "==", body.get("season"))],
        limit=1,
    )
    if not rates:
        raise HTTPException(
            status_code=404,
            detail={"code": "RATE_NOT_FOUND", "message": "No premium rate for this crop/season", "fieldErrors": {}},
        )
    rate = rates[0]
    acres = float(body.get("landAreaAcres", 0))
    sum_insured = rate["sumInsuredPerAcre"] * acres
    farmer_premium = round(sum_insured * rate["farmerSharePercent"] / 100, 2)
    govt_subsidy = round(sum_insured * (rate["totalActuarialRatePercent"] - rate["farmerSharePercent"]) / 100, 2)

    policies = await db.list_subdocs(_policies_path(uid))
    year = datetime.now(timezone.utc).year
    policy_number = f"PMFBY-{year}-{len(policies) + 1:04d}"
    start_fmt, end_fmt = COVERAGE_WINDOWS[body["season"]]
    policy_id = f"policy_{uuid4().hex[:10]}"
    doc = {
        "id": policy_id,
        "policyNumber": policy_number,
        "schemeName": "PMFBY",
        "cropName": body["cropName"],
        "season": body["season"],
        "year": year,
        "landAreaAcres": acres,
        "sumInsured": sum_insured,
        "farmerPremium": farmer_premium,
        "govtSubsidy": govt_subsidy,
        "status": "active",
        "insuranceCompany": "AIC of India",
        "coverageStartDate": start_fmt.format(year=year),
        "coverageEndDate": end_fmt.format(year=year, next_year=year + 1),
        "bankName": user.get("bankName", ""),
        "kccAccountNo": user.get("kccAccountNo", ""),
        "certificateUrl": None,
        "createdAt": _now_iso(),
    }
    await db.set_subdoc_at(_policies_path(uid), policy_id, doc)
    return doc


@router.get("/policies/{policy_id}/certificate")
async def policy_certificate(policy_id: str, user: dict = Depends(require_roles(*ROLES))):
    uid = user["id"]
    policy = await db.get_subdoc_at(_policies_path(uid), policy_id)
    if policy is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "POLICY_NOT_FOUND", "message": "Policy not found", "fieldErrors": {}},
        )
    path = reports_service.build_policy_certificate_pdf(policy)
    url = reports_service.upload_to_storage(path, f"certificates/{uid}/{policy_id}.pdf")
    policy["certificateUrl"] = url
    await db.set_subdoc_at(_policies_path(uid), policy_id, policy)
    return {"certificateUrl": url}


@router.get("/rates")
async def list_rates(season: str | None = None, crop: str | None = None, page: int = 1, pageSize: int = 20, user: dict = Depends(require_roles(*ROLES))):
    rates = await db.query("insurance_rates", [], limit=1000)
    if season:
        rates = [r for r in rates if r.get("season") == season]
    if crop:
        rates = [r for r in rates if r.get("cropName") == crop]
    total = len(rates)
    page_size = max(1, min(pageSize, 50))
    start = (max(1, page) - 1) * page_size
    return {"data": rates[start : start + page_size], "page": page, "pageSize": page_size, "total": total}


@router.post("/claims", status_code=201)
async def submit_claim(
    policyId: str = Form(...),
    cropName: str = Form(...),
    calamityType: str = Form(...),
    dateOfDamage: str = Form(...),
    cropStage: str = Form(...),
    estimatedLossPercent: float = Form(...),
    gpsCoordinates: str = Form(...),
    village: str = Form(...),
    damagePhotos: list[UploadFile] = File(...),
    user: dict = Depends(require_roles(*ROLES)),
):
    uid = user["id"]
    if estimatedLossPercent < 0 or estimatedLossPercent > 100:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "estimatedLossPercent must be 0–100", "fieldErrors": {"estimatedLossPercent": "must be 0–100"}},
        )
    if not damagePhotos:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "At least one damage photo is required", "fieldErrors": {"damagePhotos": "at least one photo required"}},
        )
    policy = await db.get_subdoc_at(_policies_path(uid), policyId)
    if policy is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "POLICY_NOT_FOUND", "message": "Policy not found", "fieldErrors": {}},
        )

    photo_urls = []
    for photo in damagePhotos[:5]:
        data = await photo.read()
        storage_service.validate_upload(photo.content_type, len(data))
        blob_path, _ = storage_service.upload_user_file(uid, data, photo.filename or "photo.jpg", photo.content_type, prefix="claims")
        photo_urls.append(storage_service.signed_download_url(blob_path))

    claim_number = await claims_service.next_claim_number(claims_service.state_code(user.get("state")))
    surveyor = claims_service.auto_assign_surveyor(user.get("district", ""))
    claim_id = uuid4().hex
    claim = {
        "id": claim_id,
        "claimNumber": claim_number,
        "policyId": policyId,
        "cropName": cropName,
        "calamityType": calamityType,
        "dateOfDamage": dateOfDamage,
        "cropStage": cropStage,
        "estimatedLossPercent": estimatedLossPercent,
        "requestedAmount": round(policy.get("sumInsured", 0) * estimatedLossPercent / 100, 2),
        "approvedAmount": None,
        "status": "intimated",
        "statusText": claims_service.STATUS_TEXT["intimated"],
        "surveyorName": surveyor["surveyorName"],
        "surveyorPhone": surveyor["surveyorPhone"],
        "surveyorVisitDate": surveyor["surveyorVisitDate"],
        "gpsCoordinates": gpsCoordinates,
        "village": village,
        "damagePhotos": photo_urls,
        "submittedAt": _now_iso(),
        "dbtTransactionId": None,
        "bankAccountLast4": (user.get("phone") or "")[-4:] or None,
        "timeline": [{"status": "intimated", "at": _now_iso(), "note": "Claim intimated within 72h window"}],
        "appealCount": 0,
        "rejectionReason": None,
    }
    await db.set_subdoc_at(_claims_path(uid), claim_id, claim)
    return {**claim, "photoGuidelines": PHOTO_GUIDELINES}


@router.get("/claims")
async def list_claims(page: int = 1, pageSize: int = 20, user: dict = Depends(require_roles(*ROLES))):
    claims = await db.list_subdocs(_claims_path(user["id"]))
    claims.sort(key=lambda c: c.get("submittedAt", ""), reverse=True)
    total = len(claims)
    page_size = max(1, min(pageSize, 50))
    start = (max(1, page) - 1) * page_size
    return {"data": claims[start : start + page_size], "page": page, "pageSize": page_size, "total": total}


@router.get("/claims/{claim_id}")
async def get_claim(claim_id: str, user: dict = Depends(require_roles(*ROLES))):
    claim = await db.get_subdoc_at(_claims_path(user["id"]), claim_id)
    if claim is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "CLAIM_NOT_FOUND", "message": "Claim not found", "fieldErrors": {}},
        )
    return claim


@router.post("/claims/{claim_id}/appeal")
async def appeal_claim(claim_id: str, body: AppealIn, user: dict = Depends(require_roles("farmer"))):
    uid = user["id"]
    claim = await db.get_subdoc_at(_claims_path(uid), claim_id)
    if claim is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "CLAIM_NOT_FOUND", "message": "Claim not found", "fieldErrors": {}},
        )
    if claim.get("status") != "rejected":
        raise HTTPException(
            status_code=409,
            detail={"code": "CLAIM_NOT_REJECTED", "message": "Only rejected claims can be appealed", "fieldErrors": {}},
        )
    merged = list(claim.get("damagePhotos", [])) + list(body.photos)
    if len(merged) > 5:
        raise HTTPException(
            status_code=422,
            detail={"code": "TOO_MANY_PHOTOS", "message": "A claim can carry at most 5 photos", "fieldErrors": {"photos": "max 5"}},
        )
    claim["damagePhotos"] = merged
    claim = await claims_service.appeal(claim, body.reason, uid)
    await db.set_subdoc_at(_claims_path(uid), claim_id, claim)
    return claim
