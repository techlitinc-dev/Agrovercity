import firebase_admin
import pytest

from app.core import db
from firebase_admin import auth as fb_auth


def _admin_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def fake_verify(monkeypatch):
    state = {"claims": {"uid": "admin-1", "email": "admin@agrovercity.in", "admin": True}}
    revoked = []

    def fake_verify(token, check_revoked=False):
        return state["claims"]

    monkeypatch.setattr(fb_auth, "verify_id_token", fake_verify)
    monkeypatch.setattr(fb_auth, "revoke_refresh_tokens", lambda uid: revoked.append(uid))

    state["revoked"] = revoked
    return state


async def test_non_admin_forbidden(client, fake_firebase, fake_users, fake_db, fake_verify):
    fake_verify["claims"] = {"uid": "user-1", "admin": False}
    for path in ("/v1/admin/login", "/v1/admin/users", "/v1/admin/analytics/summary"):
        resp = await client.post(path, headers=_admin_header("tok")) if path.endswith("login") else await client.get(path, headers=_admin_header("tok"))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "ADMIN_REQUIRED"


async def test_admin_login_ok(client, fake_firebase, fake_users, fake_db, fake_verify):
    resp = await client.post("/v1/admin/login", headers=_admin_header("tok"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["admin"] is True
    assert body["email"] == "admin@agrovercity.in"


async def test_block_user_revokes_tokens(client, fake_firebase, fake_users, fake_db, fake_verify):
    fake_db["users"]["uid-1"] = {"id": "uid-1", "name": "Ramesh", "status": "active"}
    resp = await client.put("/v1/admin/users/uid-1/status", json={"status": "blocked"}, headers=_admin_header("tok"))
    assert resp.status_code == 200
    assert fake_db["users"]["uid-1"]["status"] == "blocked"
    assert fake_verify["revoked"] == ["uid-1"]


async def test_approve_rate_feeds_widget(client, fake_firebase, fake_users, fake_db, fake_verify):
    from app.core import cache

    fake_db["vyapari_rates_pending"]["rate-1"] = {
        "id": "rate-1", "sellerId": "uid-3", "crop": "Tomato", "rateDisplay": "₹24/kg",
        "mandiName": "Nashik Mandi", "status": "pending", "createdAt": "2026-09-17T00:00:00Z",
    }
    redis = await cache.get_redis()
    await redis.set("vyapari_rates:all", "cached")

    resp = await client.post("/v1/admin/rates/rate-1/approve", headers=_admin_header("tok"))
    assert resp.status_code == 200
    assert fake_db["vyapari_rates"]["rate-1"]["status"] == "approved"
    assert fake_db["vyapari_rates_pending"]["rate-1"]["status"] == "approved"
    assert await redis.get("vyapari_rates:all") is None
    await redis.delete("vyapari_rates:all")


async def test_reject_rate(client, fake_firebase, fake_users, fake_db, fake_verify):
    fake_db["vyapari_rates_pending"]["rate-2"] = {"id": "rate-2", "status": "pending", "crop": "Onion"}
    resp = await client.post(
        "/v1/admin/rates/rate-2/reject",
        json={"reason": "भाव असत्यापित"},
        headers=_admin_header("tok"),
    )
    assert resp.status_code == 200
    assert fake_db["vyapari_rates_pending"]["rate-2"]["rejectionReason"] == "भाव असत्यापित"


async def test_claim_illegal_transition_409(client, fake_firebase, fake_users, fake_db, fake_verify):
    fake_db["users"]["uid-1"] = {"id": "uid-1"}
    fake_db["users/uid-1/insurance_claims"]["c1"] = {
        "id": "c1", "claimNumber": "CLM-2026-MH-0001", "status": "intimated", "statusText": "", "timeline": [],
    }

    resp = await client.put(
        "/v1/admin/claims/uid-1/c1",
        json={"newStatus": "dbtApproved"},
        headers=_admin_header("tok"),
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ILLEGAL_STATUS_TRANSITION"

    chain = ["surveyorAssigned", "fieldAssessed", "dbtApproved"]
    for status in chain:
        resp = await client.put("/v1/admin/claims/uid-1/c1", json={"newStatus": status}, headers=_admin_header("tok"))
        assert resp.status_code == 200

    resp = await client.put(
        "/v1/admin/claims/uid-1/c1",
        json={"newStatus": "disbursed"},
        headers=_admin_header("tok"),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "DISBURSAL_FIELDS_REQUIRED"

    resp = await client.put(
        "/v1/admin/claims/uid-1/c1",
        json={"newStatus": "disbursed", "approvedAmount": 22400, "dbtTransactionId": "DBT123"},
        headers=_admin_header("tok"),
    )
    assert resp.status_code == 200
    assert fake_db["users/uid-1/insurance_claims"]["c1"]["status"] == "disbursed"


async def test_content_cms_whitelist(client, fake_firebase, fake_users, fake_db, fake_verify):
    resp = await client.post("/v1/admin/content/news", json={"category": "x"}, headers=_admin_header("tok"))
    assert resp.status_code == 422

    resp = await client.post("/v1/admin/content/foobar", json={"title": "x"}, headers=_admin_header("tok"))
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "UNKNOWN_COLLECTION"

    resp = await client.post("/v1/admin/content/news", json={"title": "Breaking", "isBreaking": True}, headers=_admin_header("tok"))
    assert resp.status_code == 201
    news_id = resp.json()["id"]

    resp = await client.put(f"/v1/admin/content/news/{news_id}", json={"title": "Updated"}, headers=_admin_header("tok"))
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated"

    resp = await client.delete(f"/v1/admin/content/news/{news_id}", headers=_admin_header("tok"))
    assert resp.status_code == 204
    assert news_id not in fake_db["news"]


async def test_analytics_summary_keys(client, fake_firebase, fake_users, fake_db, fake_verify):
    from app.core import cache

    redis = await cache.get_redis()
    await redis.delete("admin:analytics")
    fake_db["users"]["u1"] = {"id": "u1", "linkedProfiles": ["farmer"], "status": "active"}
    fake_db["users"]["u2"] = {"id": "u2", "linkedProfiles": ["transport"], "status": "active"}

    calls = 0
    original_query = db.query

    async def counting_query(collection, filters, limit=100):
        nonlocal calls
        calls += 1
        return await original_query(collection, filters, limit)

    async def wrapper(collection, filters, limit=100):
        return await counting_query(collection, filters, limit)

    db.query = wrapper

    resp = await client.get("/v1/admin/analytics/summary", headers=_admin_header("tok"))
    assert resp.status_code == 200
    body = resp.json()
    assert {"totalUsers", "usersByPersona", "bookings", "orders", "claimsByStatus", "pendingRates"} <= set(body)

    calls_before = calls
    resp = await client.get("/v1/admin/analytics/summary", headers=_admin_header("tok"))
    assert resp.status_code == 200
    assert calls == calls_before
    await redis.delete("admin:analytics")


async def test_users_persona_filter(client, fake_firebase, fake_users, fake_db, fake_verify):
    fake_db["users"]["u1"] = {"id": "u1", "name": "A", "linkedProfiles": ["farmer"], "activeProfile": "farmer", "status": "active", "agriCoins": 0, "createdAt": "2026-01-01"}
    fake_db["users"]["u2"] = {"id": "u2", "name": "B", "linkedProfiles": ["transport"], "activeProfile": "transport", "status": "active", "agriCoins": 0, "createdAt": "2026-01-02"}

    resp = await client.get("/v1/admin/users", params={"persona": "farmer"}, headers=_admin_header("tok"))
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["id"] == "u1"


async def test_admin_rates_unknown_id_404(client, fake_firebase, fake_users, fake_db, fake_verify):
    resp = await client.post("/v1/admin/rates/bogus/approve", headers=_admin_header("tok"))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RATE_NOT_FOUND"


async def test_kyc_pending_verify_reject(client, fake_firebase, fake_users, fake_db, fake_verify):
    fake_db["vehicles"]["veh-1"] = {"id": "veh-1", "docStatus": "pending", "ownerId": "uid-5", "registrationNo": "MH15AB1234"}
    fake_db["equipment"]["eq-1"] = {"id": "eq-1", "docStatus": "pending", "ownerId": "uid-6", "name": "Tractor 35HP"}

    resp = await client.get("/v1/admin/kyc/pending", headers=_admin_header("tok"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    kinds = {r["entityKind"] for r in body["data"]}
    assert kinds == {"vehicle", "equipment"}

    resp = await client.post("/v1/admin/kyc/veh-1/verify", headers=_admin_header("tok"))
    assert resp.status_code == 200
    assert fake_db["vehicles"]["veh-1"]["docStatus"] == "verified"
    assert "verifiedAt" in fake_db["vehicles"]["veh-1"]

    resp = await client.post("/v1/admin/kyc/eq-1/reject", json={"reason": "RC मेल नहीं खाती"}, headers=_admin_header("tok"))
    assert resp.status_code == 200
    assert fake_db["equipment"]["eq-1"]["docStatus"] == "rejected"
    assert fake_db["equipment"]["eq-1"]["rejectionReason"] == "RC मेल नहीं खाती"

    resp = await client.post("/v1/admin/kyc/unknown-id/verify", headers=_admin_header("tok"))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "KYC_ENTITY_NOT_FOUND"


async def test_broadcast_dry_run_and_segmented_send(client, fake_firebase, fake_users, fake_db, fake_verify, monkeypatch):
    fake_db["users"]["u1"] = {"id": "u1", "linkedProfiles": ["farmer"], "district": "Nashik"}
    fake_db["users"]["u2"] = {"id": "u2", "linkedProfiles": ["seller"], "district": "Nashik"}
    fake_db["users"]["u3"] = {"id": "u3", "linkedProfiles": ["farmer"], "district": "Pune"}

    from app.services import fcm as fcm_mod

    sent_to = []

    async def fake_send(uid, title, body, data={}):
        sent_to.append(uid)
        return 1

    monkeypatch.setattr(fcm_mod, "send_to_user", fake_send)

    resp = await client.post(
        "/v1/admin/broadcast",
        json={"segment": {"role": "farmer"}, "title": "मौसम चेतावनी", "body": "बारिश", "dryRun": True},
        headers=_admin_header("tok"),
    )
    assert resp.status_code == 200
    assert resp.json() == {"targetedCount": 2}
    assert sent_to == []

    resp = await client.post(
        "/v1/admin/broadcast",
        json={"segment": {"role": "farmer", "district": "Pune"}, "title": "मौसम चेतावनी", "body": "बारिश"},
        headers=_admin_header("tok"),
    )
    assert resp.status_code == 200
    assert resp.json() == {"targetedCount": 1, "sent": 1}
    assert sent_to == ["u3"]

    resp = await client.post("/v1/admin/broadcast", json={"title": "t"}, headers=_admin_header("tok"))
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "SEGMENT_REQUIRED"


async def test_admin_settlements_lifecycle(client, fake_firebase, fake_users, fake_db, fake_verify):
    fake_db["settlements"]["s1"] = {"id": "s1", "kind": "transport", "status": "pending", "periodStart": "2026-09-01"}
    fake_db["settlements"]["s2"] = {"id": "s2", "kind": "equipment", "status": "approved", "periodStart": "2026-09-02"}

    resp = await client.get("/v1/admin/settlements", headers=_admin_header("tok"))
    assert resp.status_code == 200
    assert resp.json()["total"] == 2

    resp = await client.get("/v1/admin/settlements", params={"status": "approved"}, headers=_admin_header("tok"))
    assert [d["id"] for d in resp.json()["data"]] == ["s2"]

    resp = await client.post("/v1/admin/settlements/s1/settle", json={"action": "approve"}, headers=_admin_header("tok"))
    assert resp.status_code == 200
    assert fake_db["settlements"]["s1"]["status"] == "approved"

    resp = await client.post("/v1/admin/settlements/s2/settle", json={"action": "mark_paid"}, headers=_admin_header("tok"))
    assert resp.status_code == 200
    assert fake_db["settlements"]["s2"]["status"] == "paid"
    assert "paidAt" in fake_db["settlements"]["s2"]

    resp = await client.post("/v1/admin/settlements/s1/settle", json={"action": "approve"}, headers=_admin_header("tok"))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ILLEGAL_STATUS_TRANSITION"

    resp = await client.post("/v1/admin/settlements/missing/settle", json={"action": "approve"}, headers=_admin_header("tok"))
    assert resp.status_code == 404


async def test_admin_reports_resolve_dismiss(client, fake_firebase, fake_users, fake_db, fake_verify):
    fake_db["reports"]["r1"] = {"id": "r1", "reportedId": "u9", "status": "open"}

    resp = await client.get("/v1/admin/reports", params={"status": "open"}, headers=_admin_header("tok"))
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    resp = await client.post(
        "/v1/admin/reports/r1/resolve",
        json={"action": "dismiss", "note": "असत्यापित शिकायत"},
        headers=_admin_header("tok"),
    )
    assert resp.status_code == 200
    assert fake_db["reports"]["r1"]["status"] == "resolved"
    assert fake_db["reports"]["r1"]["resolution"] == "dismiss"

    resp = await client.post("/v1/admin/reports/r1/resolve", json={"action": "bogus"}, headers=_admin_header("tok"))
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    resp = await client.post("/v1/admin/reports/missing/resolve", json={"action": "dismiss"}, headers=_admin_header("tok"))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "REPORT_NOT_FOUND"


async def test_admin_reports_resolve_block_blocks_user(client, fake_firebase, fake_users, fake_db, fake_verify):
    fake_db["reports"]["r2"] = {"id": "r2", "reportedId": "u9", "status": "open"}
    fake_db["users"]["u9"] = {"id": "u9", "status": "active"}

    resp = await client.post("/v1/admin/reports/r2/resolve", json={"action": "block"}, headers=_admin_header("tok"))
    assert resp.status_code == 200
    assert fake_db["reports"]["r2"]["resolution"] == "block"
    assert fake_db["users"]["u9"]["status"] == "blocked"
    assert fake_verify["revoked"] == ["u9"]
