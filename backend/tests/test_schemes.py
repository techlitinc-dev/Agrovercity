from app.data.schemes_seed import seed_schemes
from app.services.eligibility import is_eligible


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users, acres=None, state=None) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    fake_users["users"]["uid-1"]["activeProfile"] = "farmer"
    fake_users["users"]["uid-1"]["id"] = "uid-1"
    if acres is not None:
        fake_users["users"]["uid-1"]["landAreaAcres"] = acres
    if state is not None:
        fake_users["users"]["uid-1"]["state"] = state
    return resp.json()["accessToken"]


async def test_eligible_only_filters(client, fake_firebase, fake_users, fake_db):
    await seed_schemes()
    access = await _login(client, fake_users, acres=5, state="Maharashtra")
    resp = await client.get("/v1/schemes", params={"eligibleOnly": "true"}, headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert all(item["eligible"] is True for item in body["data"])
    assert all("eligibilityRules" not in item for item in body["data"])


async def test_eligibility_service_units():
    user = {"landAreaAcres": 5, "state": "Maharashtra", "kccLimit": 0}
    assert is_eligible(user, {"maxLandAcres": 10}) is True
    assert is_eligible(user, {"maxLandAcres": 3}) is False
    assert is_eligible(user, {"states": ["Punjab"]}) is False
    assert is_eligible(user, {"requiresKcc": True}) is False
    assert is_eligible(user, {"unknownRule": 1}) is True
    assert is_eligible(user, {}) is True


async def test_apply_creates_application(client, fake_firebase, fake_users, fake_db):
    await seed_schemes()
    access = await _login(client, fake_users, acres=5, state="Maharashtra")
    resp = await client.post("/v1/schemes/pm-kisan/apply", json={"documentIds": []}, headers=_auth_header(access))
    assert resp.status_code == 201
    assert resp.json() == {"applicationId": "pm-kisan", "status": "submitted"}
    assert fake_db["users/uid-1/scheme_applications"]["pm-kisan"]["status"] == "submitted"


async def test_apply_twice_409(client, fake_firebase, fake_users, fake_db):
    await seed_schemes()
    access = await _login(client, fake_users, acres=5, state="Maharashtra")
    body = {"documentIds": []}
    assert (await client.post("/v1/schemes/pmfby/apply", json=body, headers=_auth_header(access))).status_code == 201
    resp = await client.post("/v1/schemes/pmfby/apply", json=body, headers=_auth_header(access))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ALREADY_APPLIED"


async def test_apply_bad_document_400(client, fake_firebase, fake_users, fake_db):
    await seed_schemes()
    access = await _login(client, fake_users, acres=5, state="Maharashtra")
    resp = await client.post("/v1/schemes/pmfby/apply", json={"documentIds": ["nope"]}, headers=_auth_header(access))
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_DOCUMENT_ID"


async def test_portals_five_https(client, fake_firebase, fake_users, fake_db):
    await seed_schemes()
    access = await _login(client, fake_users, acres=5, state="Maharashtra")
    resp = await client.get("/v1/schemes/portals", headers=_auth_header(access))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 5
    assert all(p["portalUrl"].startswith("https://") for p in data)
