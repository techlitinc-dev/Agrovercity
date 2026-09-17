from typing import Any

from google.cloud import firestore

from app.core.config import settings

# Firestore approach: google.cloud.firestore.AsyncClient — no Firebase Admin init needed for Firestore.
_client: firestore.AsyncClient | None = None


def get_db() -> firestore.AsyncClient:
    global _client
    if _client is None:
        _client = firestore.AsyncClient(project=settings.firebase_project_id)
    return _client


async def get_doc(collection: str, doc_id: str) -> dict | None:
    snap = await get_db().collection(collection).document(doc_id).get()
    if not snap.exists:
        return None
    return snap.to_dict()


async def set_doc(collection: str, doc_id: str, data: dict):
    await get_db().collection(collection).document(doc_id).set(data)


async def delete_doc(collection: str, doc_id: str):
    await get_db().collection(collection).document(doc_id).delete()


async def query(
    collection: str,
    filters: list[tuple[str, str, Any]],
    limit: int = 100,
) -> list[dict]:
    q = get_db().collection(collection)
    for field, op, value in filters:
        q = q.where(field, op, value)
    docs = await q.limit(limit).get()
    return [d.to_dict() for d in docs]
