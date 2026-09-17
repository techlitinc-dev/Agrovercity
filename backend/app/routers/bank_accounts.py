"""Bank accounts (payout accounts).

Firestore layout: users/{uid}/bank_accounts/{id} stores the FULL accountNumber.
Encryption at rest is provided by Firestore (AES-256/GMEK by default).
Never log full account numbers — log the masked form only.
"""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response

from app.core import db
from app.core.deps import current_user_id
from app.models.bank_accounts import BankAccountIn
from app.services.bank_verify import get_bank_verify_adapter

router = APIRouter(prefix="/bank-accounts", tags=["bank-accounts"])


def _accounts_path(uid: str) -> str:
    return f"users/{uid}/bank_accounts"


def _masked(account_number: str) -> str:
    return "XXXX" + account_number[-4:]


def _out(doc: dict) -> dict:
    return {
        **{k: v for k, v in doc.items() if k != "accountNumber"},
        "accountNumberMasked": _masked(doc["accountNumber"]),
    }


@router.get("")
async def list_accounts(page: int = 1, pageSize: int = 20, uid: str = Depends(current_user_id)):
    accounts = await db.list_subdocs(_accounts_path(uid))
    accounts.sort(key=lambda a: (not a.get("isPrimary", False), a.get("createdAt", "")))
    total = len(accounts)
    page_size = max(1, min(pageSize, 50))
    start = (max(1, page) - 1) * page_size
    return {"data": [_out(a) for a in accounts[start : start + page_size]], "page": page, "pageSize": page_size, "total": total}


@router.post("", status_code=201)
async def create_account(body: BankAccountIn, uid: str = Depends(current_user_id)):
    existing = await db.list_subdocs(_accounts_path(uid))
    account_id = f"acc_{uuid4().hex[:10]}"
    doc = {
        "id": account_id,
        **body.model_dump(),
        "isPrimary": len(existing) == 0,
        "verifyStatus": "unverified",
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    await db.set_subdoc_at(_accounts_path(uid), account_id, doc)
    return _out(doc)


@router.post("/{account_id}/verify")
async def verify_account(account_id: str, uid: str = Depends(current_user_id)):
    account = await db.get_subdoc_at(_accounts_path(uid), account_id)
    if account is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "BANK_ACCOUNT_NOT_FOUND", "message": "Bank account not found", "fieldErrors": {}},
        )
    account["verifyStatus"] = "pending"
    await db.set_subdoc_at(_accounts_path(uid), account_id, account)
    adapter = get_bank_verify_adapter()
    result = await adapter.penny_drop(account["accountNumber"], account["ifsc"], account["accountHolder"])
    account["verifyStatus"] = "verified" if result.get("verified") else "failed"
    await db.set_subdoc_at(_accounts_path(uid), account_id, account)
    return _out(account)


@router.post("/{account_id}/set-primary")
async def set_primary(account_id: str, uid: str = Depends(current_user_id)):
    account = await db.get_subdoc_at(_accounts_path(uid), account_id)
    if account is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "BANK_ACCOUNT_NOT_FOUND", "message": "Bank account not found", "fieldErrors": {}},
        )
    accounts = await db.list_subdocs(_accounts_path(uid))
    for a in accounts:
        if a["id"] != account_id and a.get("isPrimary"):
            a["isPrimary"] = False
            await db.set_subdoc_at(_accounts_path(uid), a["id"], a)
    account["isPrimary"] = True
    await db.set_subdoc_at(_accounts_path(uid), account_id, account)
    return {"primaryId": account_id}


@router.delete("/{account_id}", status_code=204)
async def delete_account(account_id: str, uid: str = Depends(current_user_id)):
    account = await db.get_subdoc_at(_accounts_path(uid), account_id)
    if account is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "BANK_ACCOUNT_NOT_FOUND", "message": "Bank account not found", "fieldErrors": {}},
        )
    await db.delete_subdoc_at(_accounts_path(uid), account_id)
    if account.get("isPrimary"):
        remaining = await db.list_subdocs(_accounts_path(uid))
        if remaining:
            oldest = min(remaining, key=lambda a: a.get("createdAt", ""))
            oldest["isPrimary"] = True
            await db.set_subdoc_at(_accounts_path(uid), oldest["id"], oldest)
    return Response(status_code=204)
