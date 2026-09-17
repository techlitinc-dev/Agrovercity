from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.core import db
from app.core.deps import current_user_id, require_profile
from app.models.diary import DiaryEntryCreated, DiaryEntryIn
from app.services import coins as coins_service
from app.services import reports as reports_service
from app.services import users as users_service

router = APIRouter(prefix="/diary", tags=["diary"])

ROLES = ("farmer", "farmLandlord")


def _entries_path(uid: str) -> str:
    return f"users/{uid}/diary_entries"


async def _user_or_403(uid: str) -> dict:
    user = await users_service.get_user(uid)
    require_profile(user, *ROLES)
    return user


def _filter_entries(entries: list[dict], type: str | None, category: str | None, from_d: str | None, to_d: str | None) -> list[dict]:
    result = entries
    if type:
        result = [e for e in result if e.get("type") == type]
    if category:
        result = [e for e in result if e.get("category") == category]
    if from_d:
        result = [e for e in result if e.get("date", "") >= from_d]
    if to_d:
        result = [e for e in result if e.get("date", "") <= to_d]
    result.sort(key=lambda e: e.get("date", ""), reverse=True)
    return result


@router.get("/entries")
async def list_entries(
    type: str | None = None,
    category: str | None = None,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    page: int = 1,
    pageSize: int = 20,
    uid: str = Depends(current_user_id),
):
    await _user_or_403(uid)
    entries = await db.list_subdocs(_entries_path(uid))
    filtered = _filter_entries(entries, type, category, from_, to)
    total = len(filtered)
    page_size = max(1, min(pageSize, 50))
    start = (max(1, page) - 1) * page_size
    return {"data": filtered[start : start + page_size], "page": page, "pageSize": page_size, "total": total}


@router.post("/entries", status_code=201)
async def create_entry(body: DiaryEntryIn, uid: str = Depends(current_user_id)):
    await _user_or_403(uid)
    entry_id = uuid4().hex
    doc = {"id": entry_id, **body.model_dump()}
    await db.set_subdoc_at(_entries_path(uid), entry_id, doc)
    coins_awarded = await coins_service.award_coins(uid, 15, "diary_entry", entry_id)
    return DiaryEntryCreated(entry={"id": entry_id, **body.model_dump()}, agriCoinsEarned=coins_awarded)


@router.delete("/entries/{entry_id}", status_code=204)
async def delete_entry(entry_id: str, uid: str = Depends(current_user_id)):
    await _user_or_403(uid)
    existing = await db.get_subdoc_at(_entries_path(uid), entry_id)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "ENTRY_NOT_FOUND", "message": "Diary entry not found", "fieldErrors": {}},
        )
    await db.delete_subdoc_at(_entries_path(uid), entry_id)
    return Response(status_code=204)


@router.get("/report")
async def diary_report(
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    uid: str = Depends(current_user_id),
):
    await _user_or_403(uid)
    today = datetime.now(timezone.utc).date()
    from_d = from_ or today.replace(day=1).isoformat()
    to_d = to or today.isoformat()
    entries = await db.list_subdocs(_entries_path(uid))
    filtered = _filter_entries(entries, None, None, from_d, to_d)
    path = reports_service.build_diary_pdf(uid, filtered, from_d, to_d)
    url = reports_service.upload_to_storage(path, f"reports/{uid}/diary_{uuid4().hex[:8]}.pdf")
    return {"reportUrl": url, "entryCount": len(filtered), "from": from_d, "to": to_d}
