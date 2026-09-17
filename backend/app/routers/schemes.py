from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.core import db
from app.core.deps import require_roles
from app.models.schemes import SchemeApplyIn
from app.services.eligibility import is_eligible

router = APIRouter(prefix="/schemes", tags=["schemes"])

ROLES = ("farmer", "farmLandlord")


def _strip_rules(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k != "eligibilityRules"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("")
async def list_schemes(category: str | None = None, eligibleOnly: bool = False, page: int = 1, pageSize: int = 20, user: dict = Depends(require_roles(*ROLES))):
    docs = await db.query("schemes", [], limit=1000)
    items = []
    for doc in docs:
        eligible = is_eligible(user, doc.get("eligibilityRules") or {})
        if category and doc.get("category") != category:
            continue
        if eligibleOnly and not eligible:
            continue
        items.append({**_strip_rules(doc), "eligible": eligible})
    total = len(items)
    page_size = max(1, min(pageSize, 50))
    start = (max(1, page) - 1) * page_size
    return {"data": items[start : start + page_size], "page": page, "pageSize": page_size, "total": total}


@router.post("/{scheme_id}/apply", status_code=201)
async def apply_scheme(scheme_id: str, body: SchemeApplyIn, user: dict = Depends(require_roles(*ROLES))):
    uid = user["id"]
    scheme = await db.get_doc("schemes", scheme_id)
    if scheme is None:
        raise HTTPException(status_code=404, detail={"code": "SCHEME_NOT_FOUND", "message": "Scheme not found", "fieldErrors": {}})
    path = f"users/{uid}/scheme_applications"
    existing = await db.get_subdoc_at(path, scheme_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail={"code": "ALREADY_APPLIED", "message": "Already applied to this scheme", "fieldErrors": {}})
    if not is_eligible(user, scheme.get("eligibilityRules") or {}):
        raise HTTPException(status_code=403, detail={"code": "NOT_ELIGIBLE", "message": "You are not eligible for this scheme", "fieldErrors": {}})
    for doc_id in body.documentIds:
        doc = await db.get_subdoc_at(f"users/{uid}/vault_documents", doc_id)
        if doc is None:
            raise HTTPException(status_code=400, detail={"code": "INVALID_DOCUMENT_ID", "message": f"Vault document {doc_id} not found", "fieldErrors": {}})
    application = {
        "applicationId": scheme_id,
        "status": "submitted",
        "documentIds": body.documentIds,
        "submittedAt": _now_iso(),
    }
    await db.set_subdoc_at(path, scheme_id, application)
    return {"applicationId": scheme_id, "status": "submitted"}


@router.get("/portals")
async def portals(user: dict = Depends(require_roles(*ROLES))):
    entries = [
        {"schemeId": "pm-kisan", "portalUrl": "https://pmkisan.gov.in"},
        {"schemeId": "pmfby", "portalUrl": "https://pmfby.gov.in"},
        {"schemeId": "soil-health-card", "portalUrl": "https://soilhealth.dac.gov.in"},
        {"schemeId": "pm-kusum", "portalUrl": "https://pmkusum.mnre.gov.in"},
        {"schemeId": "enam", "portalUrl": "https://enam.gov.in"},
    ]
    return {"data": entries}
