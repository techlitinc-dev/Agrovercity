import re

from app.data.insurance_seed import seed_insurance_rates


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users, profile="farmer") -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    fake_users["users"]["uid-1"]["activeProfile"] = profile
    fake_users["users"]["uid-1"]["id"] = "uid-1"
    return resp.json()["accessToken"]


async def test_policies_seeds_demo_on_first_read(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.get("/v1/insurance/policies", headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["data"][0]["policyNumber"] == "PMFBY-2026-0001"

    resp = await client.get("/v1/insurance/policies", headers=_auth_header(access))
    assert resp.json()["total"] == 1


async def test_apply_computes_premium_exactly(client, fake_firebase, fake_users, fake_db):
    await seed_insurance_rates()
    access = await _login(client, fake_users)
    resp = await client.post(
        "/v1/insurance/policies/apply",
        json={"cropName": "Wheat", "season": "Kharif", "landAreaAcres": 2},
        headers=_auth_header(access),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["sumInsured"] == 80000
    assert body["farmerPremium"] == 1600.0
    assert body["govtSubsidy"] == 8400.0
    assert re.fullmatch(r"PMFBY-\d{4}-\d{4}", body["policyNumber"])


async def test_apply_unknown_crop_404(client, fake_firebase, fake_users, fake_db):
    await seed_insurance_rates()
    access = await _login(client, fake_users)
    resp = await client.post(
        "/v1/insurance/policies/apply",
        json={"cropName": "Dragonfruit", "season": "Kharif", "landAreaAcres": 2},
        headers=_auth_header(access),
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RATE_NOT_FOUND"


async def test_certificate_returns_url(client, fake_firebase, fake_users, fake_db, monkeypatch):
    from app.services import reports as reports_service

    def fake_upload(local_path, dest_path):
        return "https://storage.example/cert.pdf"

    monkeypatch.setattr(reports_service, "upload_to_storage", fake_upload)
    access = await _login(client, fake_users)
    policies = (await client.get("/v1/insurance/policies", headers=_auth_header(access))).json()["data"]

    resp = await client.get(f"/v1/insurance/policies/{policies[0]['id']}/certificate", headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json()["certificateUrl"] == "https://storage.example/cert.pdf"
    assert fake_db["users/uid-1/insurance_policies"][policies[0]["id"]]["certificateUrl"]


async def test_rates_filter_by_season(client, fake_firebase, fake_users, fake_db):
    await seed_insurance_rates()
    access = await _login(client, fake_users)
    resp = await client.get("/v1/insurance/rates", params={"season": "Kharif"}, headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert all(r["season"] == "Kharif" for r in body["data"])


async def test_forbidden_for_seller(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users, profile="seller")
    resp = await client.get("/v1/insurance/policies", headers=_auth_header(access))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN_ROLE"


async def test_policy_number_increments(client, fake_firebase, fake_users, fake_db):
    await seed_insurance_rates()
    access = await _login(client, fake_users)
    body = {"cropName": "Wheat", "season": "Kharif", "landAreaAcres": 2}
    first = (await client.post("/v1/insurance/policies/apply", json=body, headers=_auth_header(access))).json()
    second = (await client.post("/v1/insurance/policies/apply", json=body, headers=_auth_header(access))).json()
    assert first["policyNumber"].endswith("-0001")
    assert second["policyNumber"].endswith("-0002")


async def test_unauthenticated_401(client, fake_firebase, fake_users, fake_db):
    resp = await client.get("/v1/insurance/policies")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "MISSING_TOKEN"
