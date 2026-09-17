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


async def set_subdoc(collection: str, doc_id: str, subcollection: str, subdoc_id: str, data: dict):
    await (
        get_db()
        .collection(collection)
        .document(doc_id)
        .collection(subcollection)
        .document(subdoc_id)
        .set(data)
    )


def _collection_ref_from_path(path: str):
    parts = path.split("/")
    ref = get_db().collection(parts[0])
    i = 1
    while i < len(parts):
        ref = ref.document(parts[i]).collection(parts[i + 1])
        i += 2
    return ref


async def set_subdoc_at(path: str, subdoc_id: str, data: dict):
    await _collection_ref_from_path(path).document(subdoc_id).set(data)


async def get_subdoc_at(path: str, subdoc_id: str) -> dict | None:
    snap = await _collection_ref_from_path(path).document(subdoc_id).get()
    if not snap.exists:
        return None
    return snap.to_dict()


async def delete_subdoc_at(path: str, subdoc_id: str):
    await _collection_ref_from_path(path).document(subdoc_id).delete()


async def list_subdocs(path: str) -> list[dict]:
    docs = await _collection_ref_from_path(path).get()
    return [d.to_dict() for d in docs]


async def list_collection_group(collection_id: str) -> list[dict]:
    """Returns [{doc, path, collection, doc_id}] where path is the parent document
    path ("" for top-level collections) and collection is the collection name."""
    docs = await get_db().collection_group(collection_id).get()
    rows = []
    for d in docs:
        parent = d.reference.parent
        if parent.parent is not None:
            rows.append({"doc": d.to_dict(), "path": parent.parent.path, "collection": collection_id, "doc_id": d.id})
        else:
            rows.append({"doc": d.to_dict(), "path": "", "collection": collection_id, "doc_id": d.id})
    return rows


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
