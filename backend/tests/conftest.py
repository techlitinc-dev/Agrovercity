import firebase_admin.auth as fb_auth
import httpx
import pytest

from app.main import app
from app.services import users as users_service


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def fake_users(monkeypatch):
    store = {}

    async def fake_get_doc(collection, doc_id):
        if collection != "users":
            return None
        return store.get(doc_id)

    async def fake_set_doc(collection, doc_id, data):
        if collection == "users":
            store[doc_id] = dict(data)

    monkeypatch.setattr(users_service, "get_doc", fake_get_doc)
    monkeypatch.setattr(users_service, "set_doc", fake_set_doc)
    return store


@pytest.fixture
def fake_firebase(monkeypatch):
    def fake_verify(token):
        return {"uid": "uid-1", "phone_number": "+919812345678"}

    monkeypatch.setattr(fb_auth, "verify_id_token", fake_verify)
    return fake_verify
