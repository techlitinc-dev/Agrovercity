import copy
from collections import defaultdict

import firebase_admin.auth as fb_auth
import httpx
import pytest

from app.core import db
from app.main import app
from app.services import users as users_service


@pytest.fixture(autouse=True)
def _reset_redis_global():
    yield
    import app.core.cache as cache_mod

    cache_mod._redis = None


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def fake_users(monkeypatch):
    store = defaultdict(dict)

    async def fake_get_doc(collection, doc_id):
        data = store.get(collection, {}).get(doc_id)
        return copy.deepcopy(data) if data is not None else None

    async def fake_set_doc(collection, doc_id, data):
        store.setdefault(collection, {})[doc_id] = copy.deepcopy(data)

    async def fake_query(collection, filters, limit=100):
        out = [copy.deepcopy(d) for d in store.get(collection, {}).values()]
        for field, op, value in filters:
            if op == "==":
                out = [d for d in out if d.get(field) == value]
        return out[:limit]

    async def fake_set_role_profile(uid, profile_type, data):
        store["role_profiles"].setdefault(uid, {})[profile_type] = copy.deepcopy(data)

    async def fake_get_role_profiles(uid):
        return copy.deepcopy(store["role_profiles"].get(uid, {}))

    monkeypatch.setattr(users_service, "get_doc", fake_get_doc)
    monkeypatch.setattr(users_service, "set_doc", fake_set_doc)
    monkeypatch.setattr(users_service, "query", fake_query)
    monkeypatch.setattr(users_service, "set_role_profile", fake_set_role_profile)
    monkeypatch.setattr(users_service, "get_role_profiles", fake_get_role_profiles)
    return store


@pytest.fixture
def fake_firebase(monkeypatch):
    def fake_verify(token):
        return {"uid": "uid-1", "phone_number": "+919812345678"}

    monkeypatch.setattr(fb_auth, "verify_id_token", fake_verify)
    return fake_verify


@pytest.fixture
def fake_db(monkeypatch):
    store = defaultdict(dict)

    async def fake_query(collection, filters, limit=100):
        docs = [copy.deepcopy(d) for d in store.get(collection, {}).values()]
        for field, op, value in filters:
            if op == "==":
                docs = [d for d in docs if d.get(field) == value]
        return docs[:limit]

    async def fake_get_doc(collection, doc_id):
        data = store.get(collection, {}).get(doc_id)
        return copy.deepcopy(data) if data is not None else None

    async def fake_set_doc(collection, doc_id, data):
        store.setdefault(collection, {})[doc_id] = copy.deepcopy(data)

    async def fake_delete_doc(collection, doc_id):
        store.get(collection, {}).pop(doc_id, None)

    async def fake_set_subdoc(collection, doc_id, subcollection, subdoc_id, data):
        store.setdefault(f"{collection}/{doc_id}/{subcollection}", {})[subdoc_id] = copy.deepcopy(data)

    async def fake_set_subdoc_at(path, subdoc_id, data):
        store.setdefault(path, {})[subdoc_id] = copy.deepcopy(data)

    async def fake_get_subdoc_at(path, subdoc_id):
        data = store.get(path, {}).get(subdoc_id)
        return copy.deepcopy(data) if data is not None else None

    async def fake_delete_subdoc_at(path, subdoc_id):
        store.get(path, {}).pop(subdoc_id, None)

    async def fake_list_subdocs(path):
        return [copy.deepcopy(d) for d in store.get(path, {}).values()]

    async def fake_list_collection_group(collection_id):
        rows = []
        for path, docs in store.items():
            if path.split("/")[-1] == collection_id:
                parent_path = "/".join(path.split("/")[:-1])
                for doc_id, doc in docs.items():
                    rows.append({"doc": copy.deepcopy(doc), "path": parent_path})
        return rows

    monkeypatch.setattr(db, "query", fake_query)
    monkeypatch.setattr(db, "get_doc", fake_get_doc)
    monkeypatch.setattr(db, "set_doc", fake_set_doc)
    monkeypatch.setattr(db, "delete_doc", fake_delete_doc)
    monkeypatch.setattr(db, "set_subdoc", fake_set_subdoc)
    monkeypatch.setattr(db, "set_subdoc_at", fake_set_subdoc_at)
    monkeypatch.setattr(db, "get_subdoc_at", fake_get_subdoc_at)
    monkeypatch.setattr(db, "delete_subdoc_at", fake_delete_subdoc_at)
    monkeypatch.setattr(db, "list_subdocs", fake_list_subdocs)
    monkeypatch.setattr(db, "list_collection_group", fake_list_collection_group)
    return store
