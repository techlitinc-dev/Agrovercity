"""User report / block routes (X9). Split from routers/users.py to respect the 300-line convention limit."""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.core import db
from app.core.deps import current_user_id
from app.services import users as users_service

router = APIRouter(prefix="/users", tags=["users"])


class ReportIn(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class BlockIn(BaseModel):
    userId: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("/{user_id}/report", status_code=201)
async def report_user(user_id: str, body: ReportIn, uid: str = Depends(current_user_id)):
    if user_id == uid:
        raise HTTPException(
            status_code=400,
            detail={"code": "CANNOT_REPORT_SELF", "message": "You cannot report yourself", "fieldErrors": {}},
        )
    target = await users_service.get_user(user_id)
    if target is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "USER_NOT_FOUND", "message": "User not found", "fieldErrors": {}},
        )
    existing = await db.query("reports", [("reporterId", "==", uid)], limit=1000)
    if any(r.get("reportedId") == user_id and r.get("status") == "open" for r in existing):
        raise HTTPException(
            status_code=409,
            detail={"code": "ALREADY_REPORTED", "message": "You already reported this user", "fieldErrors": {}},
        )
    report_id = str(uuid4())
    await db.set_doc(
        "reports",
        report_id,
        {
            "id": report_id,
            "reporterId": uid,
            "reportedId": user_id,
            "reason": body.reason,
            "status": "open",
            "createdAt": _now_iso(),
        },
    )
    return {"reported": True}


@router.get("/me/blocks")
async def list_blocks(uid: str = Depends(current_user_id)):
    docs = await db.list_subdocs(f"users/{uid}/blocks")
    items = []
    for doc in docs:
        target = await users_service.get_user(doc["id"])
        items.append({"userId": doc["id"], "name": (target or {}).get("name"), "blockedAt": doc.get("at")})
    return {"data": items, "page": 1, "pageSize": 50, "total": len(items)}


@router.post("/me/blocks", status_code=201)
async def block_user(body: BlockIn, uid: str = Depends(current_user_id)):
    if body.userId == uid:
        raise HTTPException(
            status_code=400,
            detail={"code": "CANNOT_BLOCK_SELF", "message": "You cannot block yourself", "fieldErrors": {}},
        )
    target = await users_service.get_user(body.userId)
    if target is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "USER_NOT_FOUND", "message": "User not found", "fieldErrors": {}},
        )
    await db.set_subdoc_at(f"users/{uid}/blocks", body.userId, {"id": body.userId, "at": _now_iso()})
    return {"blocked": True}


@router.delete("/me/blocks/{block_user_id}", status_code=204)
async def unblock_user(block_user_id: str, uid: str = Depends(current_user_id)):
    await db.delete_subdoc_at(f"users/{uid}/blocks", block_user_id)
    return Response(status_code=204)
