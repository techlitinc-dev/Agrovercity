import re

import pytest

from app.services.claims import STATUS_TEXT, advance_status


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


PNG_1KB = b"\x89PNG\r\n\x1a\n" + b"x" * 1000


async def _login(client, fake_users) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    fake_users["users"]["uid-1"]["activeProfile"] = "farmer"
    fake_users["users"]["uid-1"]["id"] = "uid-1"
    fake_users["users"]["uid-1"]["state"] = "Maharashtra"
    return resp.json()["accessToken"]


async def _policy_id(client, access) -> str:
    policies = (await client.get("/v1/insurance/policies", headers=_auth_header(access))).json()["data"]
    return policies[0]["id"]


def _files(n=2, size=len(PNG_1KB)):
    return [("damagePhotos", (f"p{i}.png", b"\x89PNG\r\n\x1a\n" + b"x" * (size - 8), "image/png")) for i in range(n)]


def _form(policy_id, **overrides) -> dict:
    return {
        "policyId": policy_id,
        "cropName": "Wheat",
        "calamityType": "hailstorm",
        "dateOfDamage": "2026-09-10",
        "cropStage": "flowering",
        "estimatedLossPercent": "40",
        "gpsCoordinates": "20.0,73.8",
        "village": "Ozarkhed",
        **overrides,
    }


@pytest.fixture
def fake_storage(monkeypatch):
    from app.services import storage as storage_service

    monkeypatch.setattr(
        storage_service,
        "upload_user_file",
        lambda uid, data, filename, content_type, prefix="claims": (f"{prefix}/{uid}/{filename}", len(data)),
    )
    monkeypatch.setattr(storage_service, "signed_download_url", lambda blob_path, minutes=60: f"file://{blob_path}")


async def test_submit_claim_with_photos(client, fake_firebase, fake_users, fake_db, fake_storage):
    access = await _login(client, fake_users)
    policy_id = await _policy_id(client, access)
    policy = next(iter(fake_db["users/uid-1/insurance_policies"].values()))

    resp = await client.post("/v1/insurance/claims", data=_form(policy_id), files=_files(2), headers=_auth_header(access))
    assert resp.status_code == 201
    body = resp.json()
    assert re.fullmatch(r"CLM-\d{4}-[A-Z]{2}-\d{4}", body["claimNumber"])
    assert body["status"] == "intimated"
    assert len(body["damagePhotos"]) == 2
    assert body["surveyorName"]
    assert body["requestedAmount"] == policy["sumInsured"] * 40 / 100


async def test_claim_foreign_policy_404(client, fake_firebase, fake_users, fake_db, fake_storage):
    other = await _login(client, fake_users)
    _ = other
    from app.services.tokens import create_access_token

    fake_users["users"]["uid-2"] = {"id": "uid-2", "activeProfile": "farmer", "linkedProfiles": ["farmer"]}
    foreign_access = create_access_token("uid-2")
    foreign_policy_id = (
        await client.get("/v1/insurance/policies", headers=_auth_header(foreign_access))
    ).json()["data"][0]["id"]

    access = await _login(client, fake_users)
    resp = await client.post("/v1/insurance/claims", data=_form(foreign_policy_id), files=_files(1), headers=_auth_header(access))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "POLICY_NOT_FOUND"


async def test_claim_no_photos_422(client, fake_firebase, fake_users, fake_db, fake_storage):
    access = await _login(client, fake_users)
    policy_id = await _policy_id(client, access)
    resp = await client.post("/v1/insurance/claims", data=_form(policy_id), files=[], headers=_auth_header(access))
    assert resp.status_code == 422


async def test_state_machine_legal():
    claim = {
        "status": "intimated",
        "statusText": STATUS_TEXT["intimated"],
        "timeline": [{"status": "intimated", "at": "2026-09-17T00:00:00Z", "note": "Claim intimated within 72h window"}],
    }
    updated = advance_status(claim, "surveyorAssigned")
    assert updated["status"] == "surveyorAssigned"
    assert updated["statusText"] == STATUS_TEXT["surveyorAssigned"]
    assert len(updated["timeline"]) == 2


async def test_state_machine_illegal():
    claim = {"status": "intimated", "statusText": "", "timeline": []}
    with pytest.raises(ValueError):
        advance_status(claim, "dbtApproved")


async def test_claim_list_and_detail(client, fake_firebase, fake_users, fake_db, fake_storage):
    access = await _login(client, fake_users)
    policy_id = await _policy_id(client, access)
    created = (
        await client.post("/v1/insurance/claims", data=_form(policy_id), files=_files(1), headers=_auth_header(access))
    ).json()

    resp = await client.get("/v1/insurance/claims", headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    resp = await client.get(f"/v1/insurance/claims/{created['id']}", headers=_auth_header(access))
    assert resp.json()["claimNumber"] == created["claimNumber"]

    resp = await client.get("/v1/insurance/claims/unknown", headers=_auth_header(access))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CLAIM_NOT_FOUND"


async def test_claim_numbers_increment(client, fake_firebase, fake_users, fake_db, fake_storage):
    access = await _login(client, fake_users)
    policy_id = await _policy_id(client, access)
    first = (await client.post("/v1/insurance/claims", data=_form(policy_id), files=_files(1), headers=_auth_header(access))).json()
    second = (await client.post("/v1/insurance/claims", data=_form(policy_id), files=_files(1), headers=_auth_header(access))).json()
    assert first["claimNumber"].endswith("-0001")
    assert second["claimNumber"].endswith("-0002")


async def test_claim_oversize_photo_413(client, fake_firebase, fake_users, fake_db, fake_storage):
    access = await _login(client, fake_users)
    policy_id = await _policy_id(client, access)
    big = [("damagePhotos", ("big.jpg", b"\xff" * (6 * 1024 * 1024), "image/jpeg"))]
    resp = await client.post("/v1/insurance/claims", data=_form(policy_id), files=big, headers=_auth_header(access))
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "FILE_TOO_LARGE"


async def test_claim_loss_percent_bounds_422(client, fake_firebase, fake_users, fake_db, fake_storage):
    access = await _login(client, fake_users)
    policy_id = await _policy_id(client, access)
    resp = await client.post(
        "/v1/insurance/claims",
        data=_form(policy_id, estimatedLossPercent="120"),
        files=_files(1),
        headers=_auth_header(access),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_claim_list_excludes_other_users(client, fake_firebase, fake_users, fake_db, fake_storage):
    access = await _login(client, fake_users)
    policy_id = await _policy_id(client, access)
    await client.post("/v1/insurance/claims", data=_form(policy_id), files=_files(1), headers=_auth_header(access))

    fake_users["users"]["uid-2"] = {"id": "uid-2", "activeProfile": "farmer", "linkedProfiles": ["farmer"]}
    from app.services.tokens import create_access_token

    resp = await client.get("/v1/insurance/claims", headers=_auth_header(create_access_token("uid-2")))
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_appeal_rejected_claim_returns_to_intimated(client, fake_firebase, fake_users, fake_db, fake_storage):
    access = await _login(client, fake_users)
    policy_id = await _policy_id(client, access)
    claim = (
        await client.post("/v1/insurance/claims", data=_form(policy_id), files=_files(1), headers=_auth_header(access))
    ).json()

    claim_id = claim["id"]
    from app.services.claims import advance_status

    stored = fake_db["users/uid-1/insurance_claims"][claim_id]
    advance_status(stored, "surveyorAssigned")
    advance_status(stored, "fieldAssessed")
    advance_status(stored, "rejected", "Insufficient evidence")
    timeline_before = len(stored["timeline"])

    resp = await client.post(
        f"/v1/insurance/claims/{claim_id}/appeal",
        json={"reason": "सर्वेयर ने गलत फसल स्टेज दर्ज की थी, नई फोटो संलग्न हैं"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "intimated"
    assert body["appealCount"] == 1
    assert len(body["timeline"]) == timeline_before + 1


async def test_appeal_non_rejected_409(client, fake_firebase, fake_users, fake_db, fake_storage):
    access = await _login(client, fake_users)
    policy_id = await _policy_id(client, access)
    claim = (
        await client.post("/v1/insurance/claims", data=_form(policy_id), files=_files(1), headers=_auth_header(access))
    ).json()

    resp = await client.post(
        f"/v1/insurance/claims/{claim['id']}/appeal",
        json={"reason": "सर्वेयर ने गलत फसल स्टेज दर्ज की थी"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CLAIM_NOT_REJECTED"


async def test_appeal_reason_too_short_422(client, fake_firebase, fake_users, fake_db, fake_storage):
    access = await _login(client, fake_users)
    policy_id = await _policy_id(client, access)
    claim = (
        await client.post("/v1/insurance/claims", data=_form(policy_id), files=_files(1), headers=_auth_header(access))
    ).json()
    fake_db["users/uid-1/insurance_claims"][claim["id"]]["status"] = "rejected"

    resp = await client.post(
        f"/v1/insurance/claims/{claim['id']}/appeal",
        json={"reason": "short"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 422


async def test_submit_response_has_photo_guidelines(client, fake_firebase, fake_users, fake_db, fake_storage):
    access = await _login(client, fake_users)
    policy_id = await _policy_id(client, access)
    resp = await client.post("/v1/insurance/claims", data=_form(policy_id), files=_files(1), headers=_auth_header(access))
    assert resp.status_code == 201
    assert len(resp.json()["photoGuidelines"]) == 3
