from scripts.seed_equipment import EQUIPMENT
from scripts.seed_fpo import FPO, POOL


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, fake_users) -> str:
    resp = await client.post("/v1/auth/firebase-verify", json={"idToken": "x"})
    assert resp.status_code == 200
    fake_users["users"]["uid-1"]["activeProfile"] = "farmer"
    fake_users["users"]["uid-1"]["id"] = "uid-1"
    return resp.json()["accessToken"]


async def test_fpo_me(client, fake_firebase, fake_users, fake_db):
    fake_db["fpos"][FPO["id"]] = FPO
    access = await _login(client, fake_users)
    resp = await client.get("/v1/fpo/me", headers=_auth_header(access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Sahyadri Shetkari FPO"
    assert body["memberCount"] == 214


async def test_pool_join_increments(client, fake_firebase, fake_users, fake_db):
    fake_db["fpo_pools"][POOL["id"]] = POOL
    access = await _login(client, fake_users)
    resp = await client.post("/v1/fpo/pools/pool-1/join", json={"units": 5}, headers=_auth_header(access))
    assert resp.status_code == 200
    assert resp.json()["bookedUnits"] == 385


async def test_pool_full_409(client, fake_firebase, fake_users, fake_db):
    fake_db["fpo_pools"][POOL["id"]] = POOL
    access = await _login(client, fake_users)
    resp = await client.post("/v1/fpo/pools/pool-1/join", json={"units": 200}, headers=_auth_header(access))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "POOL_FULL"


async def test_machinery_calendar(client, fake_firebase, fake_users, fake_db):
    for doc in EQUIPMENT:
        fake_db["equipment"][doc["id"]] = doc
    access = await _login(client, fake_users)
    resp = await client.get("/v1/fpo/machinery", headers=_auth_header(access))
    assert resp.status_code == 200
    data = resp.json()["data"]
    eq1 = next(d for d in data if d["equipmentId"] == "eq-1")
    assert len(eq1["days"]) == 7
    assert all(len(slots) == 4 for slots in eq1["days"].values())
    assert all(d["equipmentId"] != "eq-2" for d in data)
