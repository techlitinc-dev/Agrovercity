from fastapi import APIRouter, Depends

from app.core import db
from app.core.deps import current_user_id

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _path(uid: str) -> str:
    return f"users/{uid}/notifications"


@router.get("")
async def list_notifications(page: int = 1, pageSize: int = 20, uid: str = Depends(current_user_id)):
    docs = await db.list_subdocs(_path(uid))
    docs.sort(key=lambda d: d.get("createdAt", ""), reverse=True)
    total = len(docs)
    page_size = max(1, min(pageSize, 50))
    start = (max(1, page) - 1) * page_size
    return {"data": docs[start : start + page_size], "page": page, "pageSize": page_size, "total": total}


@router.post("/read")
async def mark_read(body: dict, uid: str = Depends(current_user_id)):
    notifications = await db.list_subdocs(_path(uid))
    ids = set(body.get("notificationIds", []))
    marked = 0
    for doc in notifications:
        if ids and doc["id"] not in ids:
            continue
        if doc.get("read"):
            continue
        doc["read"] = True
        await db.set_subdoc_at(_path(uid), doc["id"], doc)
        marked += 1
    return {"markedRead": marked}
