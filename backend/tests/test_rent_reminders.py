import pytest

from app.routers import jobs as jobs_router
from app.services import rent_reminders as rent_reminders_service
from app.services.settlements import last_iso_week


def _seed_due_lease(fake_db, lease_id="lease-1", landlord_uid="uid-2", month="2026-09"):
    fake_db[f"users/{landlord_uid}/land_leases"][lease_id] = {
        "id": lease_id,
        "tenantName": "Sunil Pawar",
        "tenantPhone": "+919822211122",
        "monthlyRentRupees": 8000,
        "startDate": "2026-07-01",
        "endDate": "2027-06-30",
        "status": "active",
    }


@pytest.fixture
def notify_calls(monkeypatch):
    calls = []

    async def fake_notify(uid, title, body, data):
        calls.append((uid, title, body, data))

    monkeypatch.setattr(rent_reminders_service, "notify", fake_notify)
    return calls


async def test_due_lease_notifies_landlord(client, fake_firebase, fake_users, fake_db, notify_calls):
    _seed_due_lease(fake_db)

    result = await rent_reminders_service.run_rent_reminders(today=__import__("datetime").date(2026, 9, 10))
    assert result == {"reminded": 1}
    uid, title, body, data = notify_calls[0]
    assert uid == "uid-2"
    assert data["type"] == "rent_reminder"
    assert "Sunil Pawar" in body


async def test_paid_month_skips(client, fake_firebase, fake_users, fake_db, notify_calls):
    _seed_due_lease(fake_db)
    fake_db["users/uid-2/land_leases/lease-1/payments"]["p1"] = {"id": "p1", "month": "2026-09", "amountRupees": 8000}

    result = await rent_reminders_service.run_rent_reminders(today=__import__("datetime").date(2026, 9, 10))
    assert result == {"reminded": 0}
    assert notify_calls == []


async def test_grace_window(client, fake_firebase, fake_users, fake_db, notify_calls):
    _seed_due_lease(fake_db)

    result = await rent_reminders_service.run_rent_reminders(today=__import__("datetime").date(2026, 9, 3))
    assert result == {"reminded": 0}


async def test_dedup_same_month(client, fake_firebase, fake_users, fake_db, notify_calls):
    _seed_due_lease(fake_db)
    fake_db["users/uid-2/notifications"]["n1"] = {
        "id": "n1",
        "data": {"type": "rent_reminder", "leaseId": "lease-1", "month": "2026-09"},
    }

    result = await rent_reminders_service.run_rent_reminders(today=__import__("datetime").date(2026, 9, 10))
    assert result == {"reminded": 0}


async def test_cron_secret_required(client, fake_firebase, fake_users, fake_db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "cron_secret", "topsecret")
    resp = await client.post("/v1/jobs/rent-reminders/run", headers={"X-Cron-Secret": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "CRON_UNAUTHORIZED"
    _ = jobs_router, last_iso_week
