import pytest

from app.routers import app_config

SEED_DOC = {
    "minSupportedVersion": "1.0.0",
    "forceUpdate": False,
    "featureFlags": {
        "liveChannels": True,
        "bnpl": False,
    },
    "maintenanceMode": False,
}


@pytest.fixture
def patch_get_doc(monkeypatch):
    async def fake_get_doc(collection: str, doc_id: str):
        return SEED_DOC

    monkeypatch.setattr(app_config, "get_doc", fake_get_doc)


async def test_app_config_shape(client, patch_get_doc):
    resp = await client.get("/v1/app-config")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {
        "minSupportedVersion",
        "forceUpdate",
        "featureFlags",
        "maintenanceMode",
    }
    assert all(isinstance(v, bool) for v in body["featureFlags"].values())


async def test_force_update_computed(client, patch_get_doc):
    resp = await client.get("/v1/app-config", params={"version": "0.9.0"})
    assert resp.status_code == 200
    assert resp.json()["forceUpdate"] is True

    resp = await client.get("/v1/app-config", params={"version": "1.2.0"})
    assert resp.status_code == 200
    assert resp.json()["forceUpdate"] is False


async def test_app_config_public(client, patch_get_doc):
    resp = await client.get("/v1/app-config")
    assert resp.status_code == 200


async def test_app_config_missing(client, monkeypatch):
    async def fake_get_doc(collection: str, doc_id: str):
        return None

    monkeypatch.setattr(app_config, "get_doc", fake_get_doc)
    resp = await client.get("/v1/app-config")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "APP_CONFIG_MISSING"
