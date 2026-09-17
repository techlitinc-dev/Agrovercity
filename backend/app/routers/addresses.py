from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response

from app.core import db
from app.core.deps import current_user_id
from app.models.addresses import AddressRequest

router = APIRouter(tags=["addresses"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_pincode(pincode: str):
    if len(pincode) != 6 or not all(c in "0123456789" for c in pincode):
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "pincode must be exactly 6 digits", "fieldErrors": {"pincode": "must be exactly 6 digits"}},
        )


async def _clear_other_defaults(uid: str, except_id: str | None = None):
    docs = await db.query("addresses", [("userId", "==", uid)], limit=1000)
    for doc in docs:
        if doc["id"] != except_id and doc.get("isDefault"):
            doc["isDefault"] = False
            await db.set_doc("addresses", doc["id"], doc)


@router.get("/addresses")
async def list_addresses(uid: str = Depends(current_user_id)):
    docs = await db.query("addresses", [("userId", "==", uid)], limit=1000)
    docs.sort(key=lambda d: (not d.get("isDefault", False), d.get("createdAt", "")))
    return {"data": docs}


@router.post("/addresses", status_code=201)
async def create_address(body: AddressRequest, uid: str = Depends(current_user_id)):
    _validate_pincode(body.pincode)
    existing = await db.query("addresses", [("userId", "==", uid)], limit=1000)
    is_default = body.isDefault or len(existing) == 0
    address_id = f"addr_{uuid4().hex[:10]}"
    doc = {
        **body.model_dump(),
        "id": address_id,
        "userId": uid,
        "isDefault": is_default,
        "createdAt": _now_iso(),
    }
    await db.set_doc("addresses", address_id, doc)
    if is_default:
        await _clear_other_defaults(uid, except_id=address_id)
    return doc


@router.put("/addresses/{address_id}")
async def update_address(address_id: str, body: AddressRequest, uid: str = Depends(current_user_id)):
    address = await db.get_doc("addresses", address_id)
    if address is None or address.get("userId") != uid:
        raise HTTPException(
            status_code=404,
            detail={"code": "ADDRESS_NOT_FOUND", "message": "Address not found", "fieldErrors": {}},
        )
    _validate_pincode(body.pincode)
    address.update(body.model_dump())
    await db.set_doc("addresses", address_id, address)
    if body.isDefault:
        await _clear_other_defaults(uid, except_id=address_id)
    return address


@router.delete("/addresses/{address_id}", status_code=204)
async def delete_address(address_id: str, uid: str = Depends(current_user_id)):
    address = await db.get_doc("addresses", address_id)
    if address is None or address.get("userId") != uid:
        raise HTTPException(
            status_code=404,
            detail={"code": "ADDRESS_NOT_FOUND", "message": "Address not found", "fieldErrors": {}},
        )
    await db.delete_doc("addresses", address_id)
    if address.get("isDefault"):
        remaining = await db.query("addresses", [("userId", "==", uid)], limit=1000)
        if remaining:
            oldest = min(remaining, key=lambda d: d.get("createdAt", ""))
            oldest["isDefault"] = True
            await db.set_doc("addresses", oldest["id"], oldest)
    return Response(status_code=204)
