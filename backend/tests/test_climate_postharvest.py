def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users, acres=None, profile="farmer") -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    fake_users["users"]["uid-1"]["activeProfile"] = profile
    fake_users["users"]["uid-1"]["id"] = "uid-1"
    if acres is not None:
        fake_users["users"]["uid-1"]["landAreaAcres"] = acres
    return resp.json()["accessToken"]


async def test_carbon_potential_math(client, fake_firebase, fake_users):
    access = await _login(client, fake_users, acres=5)
    resp = await client.get("/v1/climate/carbon-potential", params={"lat": 20.0, "lng": 73.8}, headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["co2eTonnes"] == 4.6
    assert body["annualIncomePotential"] == 9200
    assert body["practices"] == ["biochar", "zero-till", "green-manure"]


async def test_resilient_varieties_filter(client, fake_firebase, fake_users):
    access = await _login(client, fake_users)
    resp = await client.get("/v1/climate/resilient-varieties", params={"crop": "rice"}, headers=_auth_header(access))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) >= 1
    assert any("Swarna" in v["variety"] for v in data)


async def test_cold_storage_list(client, fake_firebase, fake_users, fake_db):
    from app.data.cold_storage_seed import seed_cold_storage

    await seed_cold_storage()
    access = await _login(client, fake_users)
    resp = await client.get("/v1/post-harvest/cold-storage", headers=_auth_header(access))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 4
    assert all({"id", "name", "distanceKm", "tempRange", "availableMT", "ratePerQuintalMonth"} <= set(item) for item in data)


async def test_grade_stub(client, fake_firebase, fake_users, monkeypatch):
    from app.services import storage as storage_service

    monkeypatch.setattr(
        storage_service,
        "upload_user_file",
        lambda uid, data, filename, content_type, prefix="grading": (f"{prefix}/{uid}/f", len(data)),
    )
    access = await _login(client, fake_users)
    resp = await client.post(
        "/v1/post-harvest/grade",
        files=[("images", ("p.png", b"\x89PNG\r\n\x1a\n" + b"x" * 500, "image/png"))],
        headers=_auth_header(access),
    )
    assert resp.status_code == 200
    assert resp.json()["grade"] == "AGMARK A"

    resp = await client.post(
        "/v1/post-harvest/grade",
        files=[("images", ("p.txt", b"text", "text/plain"))],
        headers=_auth_header(access),
    )
    assert resp.status_code == 415


async def test_grade_max_3_images_422(client, fake_firebase, fake_users):
    access = await _login(client, fake_users)
    images = [("images", (f"p{i}.png", b"\x89PNG\r\n\x1a\n" + b"x" * 100, "image/png")) for i in range(4)]
    resp = await client.post("/v1/post-harvest/grade", files=images, headers=_auth_header(access))
    assert resp.status_code == 422


async def test_carbon_forbidden_for_transport(client, fake_firebase, fake_users):
    access = await _login(client, fake_users, profile="transport")
    resp = await client.get("/v1/climate/carbon-potential", headers=_auth_header(access))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN_ROLE"
