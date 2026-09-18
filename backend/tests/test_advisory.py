from app.data.livestock_seed import seed_livestock
from app.services.advisory import current_season


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    fake_users["users"]["uid-1"]["activeProfile"] = "farmer"
    fake_users["users"]["uid-1"]["id"] = "uid-1"
    return resp.json()["accessToken"]


async def test_saturation_green_when_empty(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.post(
        "/v1/advisory/saturation",
        json={"crop": "onion", "district": "Nashik", "lat": 20.0, "lng": 73.8},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sowingCount"] == 0
    assert body["riskLevel"] == "green"


async def test_saturation_red_when_crowded(client, fake_firebase, fake_users, fake_db):
    for i in range(65):
        fake_db["crop_cycles"][f"c{i}"] = {"id": f"c{i}", "crop": "onion", "district": "Nashik", "userId": f"u{i}"}
    access = await _login(client, fake_users)
    resp = await client.post(
        "/v1/advisory/saturation",
        json={"crop": "onion", "district": "Nashik", "lat": 20.0, "lng": 73.8},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["riskLevel"] == "red"
    assert body["predictedPrice"] < 1450


async def test_sowing_intent_recorded_opt_in(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    await client.post(
        "/v1/advisory/saturation",
        json={"crop": "wheat", "district": "Nashik", "lat": 20.0, "lng": 73.8},
        headers=_auth_header(access),
    )
    season = current_season()
    assert f"uid-1_wheat_{season}" in fake_db["crop_cycles"]

    await client.post(
        "/v1/advisory/saturation",
        json={"crop": "onion", "district": "Nashik", "lat": 20.0, "lng": 73.8, "shareSowingIntent": False},
        headers=_auth_header(access),
    )
    assert not any(doc["crop"] == "onion" and doc.get("userId") == "uid-1" for doc in fake_db["crop_cycles"].values())


async def test_disease_scan_stub(client, fake_firebase, fake_users, fake_db, monkeypatch):
    from app.services import storage as storage_service

    monkeypatch.setattr(
        storage_service,
        "upload_user_file",
        lambda uid, data, filename, content_type, prefix="scans": (f"{prefix}/{uid}/f", len(data)),
    )
    access = await _login(client, fake_users)
    resp = await client.post(
        "/v1/advisory/disease-scan",
        files={"file": ("leaf.png", b"\x89PNG\r\n\x1a\n" + b"x" * 500, "image/png")},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert results[0]["diseaseName"] == "Early Blight"

    resp = await client.post(
        "/v1/advisory/disease-scan",
        files={"file": ("leaf.txt", b"plain", "text/plain")},
        headers=_auth_header(access),
    )
    assert resp.status_code == 415


async def test_npk_deficit_math(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.post(
        "/v1/advisory/npk",
        json={"n": 40, "p": 20, "k": 10, "crop": "wheat", "soilType": "black"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ureaKgPerAcre"] > 0
    assert body["dapKgPerAcre"] > 0
    assert body["mopKgPerAcre"] > 0
    assert body["recommendations"]


async def test_intent_recorded_with_flag(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    await client.put(
        "/v1/users/me/consents",
        json={"dataSharing": True, "location": True, "marketing": False},
        headers=_auth_header(access),
    )
    resp = await client.post(
        "/v1/advisory/sowing-intent",
        json={"crop": "wheat", "plannedDate": "2026-11-01"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 201
    assert resp.json() == {"recorded": True, "isIntent": True}
    season = current_season()
    assert fake_db["crop_cycles"][f"uid-1_wheat_{season}"]["isIntent"] is True


async def test_intent_without_consent_403(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.post(
        "/v1/advisory/sowing-intent",
        json={"crop": "wheat", "plannedDate": "2026-11-01"},
        headers=_auth_header(access),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "CONSENT_REQUIRED"


async def test_intent_feeds_saturation_count(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    await client.put(
        "/v1/users/me/consents",
        json={"dataSharing": True, "location": True, "marketing": False},
        headers=_auth_header(access),
    )
    await client.post(
        "/v1/advisory/sowing-intent",
        json={"crop": "wheat", "plannedDate": "2026-11-01"},
        headers=_auth_header(access),
    )
    resp = await client.post(
        "/v1/advisory/saturation",
        json={"crop": "wheat", "district": "", "lat": 20.0, "lng": 73.8, "shareSowingIntent": False},
        headers=_auth_header(access),
    )
    assert resp.json()["sowingCount"] >= 1


async def test_pest_radar_alerts(client, fake_firebase, fake_users, fake_db):
    access = await _login(client, fake_users)
    resp = await client.get(
        "/v1/advisory/pest-radar",
        params={"lat": 20.0, "lng": 73.8, "radiusKm": 5},
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert body["data"][0]["disease"] == "Pink bollworm"
    assert body["data"][0]["riskLevel"] == "yellow"
    assert all(a["riskLevel"] in {"green", "yellow", "red"} for a in body["data"])
