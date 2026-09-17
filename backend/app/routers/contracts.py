from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.core import db
from app.core.deps import require_roles
from app.core.security import verify_mpin
from app.models.contracts import AcceptContractRequest

router = APIRouter(prefix="/contracts", tags=["contracts"])

CONTRACT_ROLES = ("farmer", "seller", "broker")
ACCEPT_ROLES = ("farmer", "seller")


@router.get("")
async def list_contracts(status: str | None = None, page: int = 1, pageSize: int = 20, user: dict = Depends(require_roles(*CONTRACT_ROLES))):
    docs = await db.query("contracts", [], limit=1000)
    if status:
        docs = [d for d in docs if d.get("status") == status]
    total = len(docs)
    page_size = max(1, min(pageSize, 50))
    start = (max(1, page) - 1) * page_size
    return {"data": docs[start : start + page_size], "page": page, "pageSize": page_size, "total": total}


@router.get("/{contract_id}")
async def get_contract(contract_id: str, user: dict = Depends(require_roles(*CONTRACT_ROLES))):
    contract = await db.get_doc("contracts", contract_id)
    if contract is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "CONTRACT_NOT_FOUND", "message": "Contract not found", "fieldErrors": {}},
        )
    return contract


@router.post("/{contract_id}/accept")
async def accept_contract(contract_id: str, body: AcceptContractRequest, user: dict = Depends(require_roles(*ACCEPT_ROLES))):
    if user.get("mpinHash") is None:
        raise HTTPException(
            status_code=409,
            detail={"code": "MPIN_NOT_SET", "message": "MPIN has not been set for this account", "fieldErrors": {}},
        )
    if not verify_mpin(body.mpin, user["mpinHash"]):
        raise HTTPException(
            status_code=401,
            detail={"code": "WRONG_MPIN", "message": "Incorrect MPIN", "fieldErrors": {}},
        )
    contract = await db.get_doc("contracts", contract_id)
    if contract is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "CONTRACT_NOT_FOUND", "message": "Contract not found", "fieldErrors": {}},
        )
    if contract.get("status") != "open":
        raise HTTPException(
            status_code=409,
            detail={"code": "CONTRACT_NOT_OPEN", "message": "Contract is no longer open", "fieldErrors": {}},
        )
    await db.set_subdoc(
        "contracts",
        contract_id,
        "acceptances",
        user["id"],
        {
            "userId": user["id"],
            "signatureData": body.signatureData,
            "consentTimestamp": body.consentTimestamp,
            "acceptedAt": datetime.now(timezone.utc).isoformat(),
        },
    )
    contract["status"] = "accepted"
    contract["acceptedBy"] = user["id"]
    await db.set_doc("contracts", contract_id, contract)
    return {"ok": True, "status": "accepted", "contractId": contract_id}
