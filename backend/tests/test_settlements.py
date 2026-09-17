import pytest

from app.routers import jobs as jobs_router


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users, uid, profile) -> str:
    if uid == "uid-1":
        resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
        assert resp.status_code == 200
        fake_users["users"]["uid-1"]["activeProfile"] = profile
        fake_users["users"]["uid-1"]["id"] = "uid-1"
        return resp.json()["accessToken"]
    fake_users["users"][uid] = {"id": uid, "activeProfile": profile, "linkedProfiles": [profile], "referralCode": f"ref_{uid[:8]}"}
    from app.services.tokens import create_access_token

    return create_access_token(uid)


def _seed_delivered_bookings(fake_db, vehicle_id="veh-1"):
    fake_db["vehicles"]["veh-1"] = {"id": "veh-1", "ownerId": "uid-2"}
    fake_db["transport_bookings"]["bk-1"] = {
        "id": "bk-1",
        "vehicleId": vehicle_id,
        "status": "delivered",
        "fare": 800,
        "date": "2026-09-02",
    }
    fake_db["transport_bookings"]["bk-2"] = {
        "id": "bk-2",
        "vehicleId": vehicle_id,
        "status": "delivered",
        "fare": 1200,
        "date": "2026-09-04",
    }


async def test_job_aggregates_transport_fares(client, fake_firebase, fake_users, fake_db):
    _seed_delivered_bookings(fake_db)
    resp = await client.post(
        "/v1/jobs/settlements/run",
        json={"periodStart": "2026-09-01", "periodEnd": "2026-09-07"},
    )
    assert resp.status_code == 200
    assert resp.json()["created"] == 1

    settlement = next(iter(fake_db["settlements"].values()))
    assert settlement["grossRupees"] == 2000
    assert settlement["commissionRupees"] == 200
    assert settlement["netRupees"] == 1800
    assert settlement["status"] == "pending"
    assert settlement["role"] == "transport"


async def test_job_idempotent_rerun(client, fake_firebase, fake_users, fake_db):
    _seed_delivered_bookings(fake_db)
    await client.post("/v1/jobs/settlements/run", json={"periodStart": "2026-09-01", "periodEnd": "2026-09-07"})
    resp = await client.post("/v1/jobs/settlements/run", json={"periodStart": "2026-09-01", "periodEnd": "2026-09-07"})
    assert resp.json()["created"] == 0
    assert len(fake_db["settlements"]) == 1


async def test_cron_secret_required(client, fake_firebase, fake_users, fake_db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "cron_secret", "topsecret")
    resp = await client.post("/v1/jobs/settlements/run")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "CRON_UNAUTHORIZED"

    resp = await client.post("/v1/jobs/settlements/run", headers={"X-Cron-Secret": "wrong"})
    assert resp.status_code == 401

    resp = await client.post("/v1/jobs/settlements/run", headers={"X-Cron-Secret": "topsecret"})
    assert resp.status_code == 200


async def test_persona_scoping(client, fake_firebase, fake_users, fake_db):
    _seed_delivered_bookings(fake_db)
    await client.post("/v1/jobs/settlements/run", json={"periodStart": "2026-09-01", "periodEnd": "2026-09-07"})

    transporter = await _login(client, fake_users, "uid-2", "transport")
    farmer = await _login(client, fake_users, "uid-1", "farmer")

    resp = await client.get("/v1/transport/settlements", headers=_auth_header(transporter))
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["data"][0]["entityId"] == "uid-2"

    resp = await client.get("/v1/transport/settlements", headers=_auth_header(farmer))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN_ROLE"


async def test_pending_recomputed_approved_untouched(client, fake_firebase, fake_users, fake_db):
    _seed_delivered_bookings(fake_db)
    await client.post("/v1/jobs/settlements/run", json={"periodStart": "2026-09-01", "periodEnd": "2026-09-07"})
    doc_id = next(iter(fake_db["settlements"]))
    fake_db["settlements"][doc_id]["status"] = "approved"

    fake_db["transport_bookings"]["bk-3"] = {
        "id": "bk-3",
        "vehicleId": "veh-1",
        "status": "delivered",
        "fare": 500,
        "date": "2026-09-05",
    }
    resp = await client.post("/v1/jobs/settlements/run", json={"periodStart": "2026-09-01", "periodEnd": "2026-09-07"})
    assert resp.json()["created"] == 0
    settlement = fake_db["settlements"][doc_id]
    assert settlement["grossRupees"] == 2000
    assert settlement["status"] == "approved"
