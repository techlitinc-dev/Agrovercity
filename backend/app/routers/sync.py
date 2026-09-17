from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.deps import current_user_id
from app.services.sync import dispatch

router = APIRouter(prefix="/sync", tags=["sync"])

MAX_OPS = 50


class SyncIn(BaseModel):
    operations: list[dict]


@router.post("")
async def sync(body: SyncIn, uid: str = Depends(current_user_id)):
    if len(body.operations) > MAX_OPS:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": f"Maximum {MAX_OPS} operations per batch", "fieldErrors": {"operations": f"max {MAX_OPS}"}},
        )
    results = []
    applied = duplicates = errors = 0
    for op in body.operations:
        result = await dispatch(uid, op)
        results.append(result)
        if result["status"] == "applied":
            applied += 1
        elif result["status"] == "duplicate":
            duplicates += 1
        else:
            errors += 1
    return {"results": results, "applied": applied, "duplicates": duplicates, "errors": errors}
