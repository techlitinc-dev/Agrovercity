# Backend Summary

Status tracker for Dev A (backend) work, day by day.

## Day 2 — Auth backend (Tasks A1–A2)

**Status: implemented — 17/17 tests passing.**

### Task A1 — POST /v1/auth/firebase-verify + JWT issue/refresh — DONE

- `backend/app/models/auth.py`: `FirebaseVerifyRequest`, `TokenPair`, `AuthResponse`, `RefreshRequest` (+ `MpinSetRequest`, `MpinVerifyRequest`, `MpinResetRequest`, `OkResponse` for A2).
- `backend/app/services/tokens.py`: `create_access_token`, `create_refresh_token` (HS256 via python-jose, `sub`/`type`/`iat`/`exp` claims), `decode_token(token, expected_type)` → 401 `INVALID_TOKEN` on JWTError or type mismatch.
- `backend/app/services/users.py`: `upsert_user_from_firebase` creates the full `users/{uid}` doc per day-file template (createdAt = UTC ISO); `get_user`; `set_mpin_hash`.
- `backend/app/routers/auth.py` (prefix `/auth`): `POST /firebase-verify` verifies the Firebase ID token, normalizes phone to `+91...`, upserts the user, returns `AuthResponse` with `mpinHash` stripped (schema: never returned); 401 `INVALID_FIREBASE_TOKEN` on `InvalidIdTokenError`. `POST /refresh` rotates both tokens.
- `main.py`: auth router mounted; **error-envelope exception handler** — every `HTTPException` with a dict detail now renders as `{ "error": { "code", "message", "fieldErrors" } }` (conventions §6). Non-dict details are wrapped as `{"code": "ERROR"}`.
- Tests (`tests/test_auth.py`, fixtures in `tests/conftest.py` — mocked `firebase_admin.auth.verify_id_token` + in-memory user store patching `app.services.users.get_doc/set_doc`): new-user verify, invalid token → 401 envelope, existing-user verify (`isNewUser: False`), refresh roundtrip, access-token-to-refresh → 401 `INVALID_TOKEN`. 5 passed.

### Task A2 — MPIN set / verify / reset — DONE

- `backend/app/core/security.py`: passlib `CryptContext` bcrypt; `hash_mpin`, `verify_mpin`, `validate_mpin_format` (4 ASCII digits, else 422 `INVALID_MPIN_FORMAT`).
- `backend/app/core/deps.py`: `current_user_id` — parses `Bearer <token>`, decodes as access token; missing/malformed header → 401 `MISSING_TOKEN`.
- Endpoints on `routers/auth.py`: `POST /mpin/set` (auth, validates format, stores bcrypt hash), `POST /mpin/verify` (auth; 409 `MPIN_NOT_SET` if no hash; 401 `WRONG_MPIN` on mismatch), `POST /mpin/reset` (public, requires fresh Firebase ID token; 404 `NOT_FOUND` if user absent).
- Tests (`tests/test_mpin.py`): set+verify happy path, wrong MPIN → 401, verify-before-set → 409, bad format → 422, reset swaps hash (old fails, new verifies). 5 passed.

### Test run (final)

```
$ cd backend && .venv/bin/pytest -v
tests/test_app_config.py  4 passed
tests/test_auth.py        5 passed
tests/test_infra.py       3 passed
tests/test_mpin.py        5 passed
17 passed, 2 warnings in 2.37s
```

### Blockers / notes

- **Dependency deviation (reported per conventions §1.7):** `bcrypt` pinned to `<4.1` in `requirements.txt`. passlib 1.7.4 is incompatible with bcrypt ≥ 4.1 (its backend detection feeds bcrypt 5 a >72-byte "password" → `ValueError`). The day file lists `passlib[bcrypt]>=1.7.4` without a pin; the pin is the minimal fix. Alternative (replacing passlib with raw `bcrypt`) would deviate further from the day file.
- **Day-1 test updated:** `test_app_config_missing` now asserts the `{"error": {"code": "APP_CONFIG_MISSING"}}` envelope instead of FastAPI's default `{"detail": ...}` — the new envelope handler (a Day-2 deliverable) changed the response shape.
- **Firebase not initialized in this environment** (no service-account JSON): live `POST /v1/auth/firebase-verify` with a garbage token returns 500 because `verify_id_token` raises `ValueError` before token parsing. With credentials present it raises `InvalidIdTokenError` → 401 envelope, which the mocked tests verify. Live happy-path testing is blocked on credentials, same as Day 1 seeding.
- `MISSING_TOKEN`, envelope shapes verified live: mpin/verify without auth → 401 envelope; health still 200.

## Day 1 — Foundation (Tasks A1–A4)

**Status: implemented — 7/7 tests passing.**

### Task A1 — Backend skeleton + docker-compose + health endpoint — DONE

- FastAPI app at `backend/app/main.py` boots under uvicorn; `GET /v1/health` → `{"status":"ok"}`; `/docs` returns Swagger UI (HTTP 200).
- `backend/app/core/config.py`: pydantic-settings `Settings` with all day-file fields (+ `sentry_dsn` from A4); reads `.env`.
- `backend/.env.example` lists every field with dev defaults, no real secrets.
- `backend/requirements.txt` with the exact day-file packages + `sentry-sdk[fastapi]>=2.14` (A4).
- venv created at `backend/.venv`, all deps installed (Python 3.14, fastapi 0.141, firebase-admin 7.5, sentry-sdk 2.69).
- `infra/docker-compose.yml`: `api` (build `../backend`, port 8000, env_file) + `redis:7-alpine` (port 6379). Docker is not installed in this environment, so the api service was exercised via local uvicorn; Redis 8.0.5 was already running locally on 6379.
- Verified: `curl http://localhost:8000/v1/health` → 200 `{"status":"ok"}`, `/docs` → 200.

### Task A2 — Firebase init, Firestore helper, Redis cache helper — DONE

- `backend/app/core/firebase.py`: `init_firebase()` — skips with a warning if the service-account JSON is missing (dev mode boots clean), guards against double init.
- `backend/app/core/db.py`: Firestore approach is `google.cloud.firestore.AsyncClient(project=...)` (documented in-file; no Admin init needed for Firestore). Helpers: `get_doc`, `set_doc`, `query` (filters as `(field, op, value)` tuples).
- `backend/app/core/cache.py`: `redis.asyncio` client with `get_redis`, `cache_get`, `cache_set(ttl)`, `cache_delete`.
- `init_firebase()` called from the startup handler in `main.py`.
- `backend/pytest.ini`: `asyncio_mode = auto`, `pythonpath = .`; shared `client` fixture in `tests/conftest.py`.
- Tests (`tests/test_infra.py`): `test_settings_load`, `test_health`, `test_cache_roundtrip` — all 3 pass against the running local Redis (no skips).

### Task A3 — GET /v1/app-config (version gate / remote config) — DONE

- `backend/app/models/app_config.py`: `AppConfigOut` (minSupportedVersion, forceUpdate, featureFlags, maintenanceMode).
- `backend/app/routers/app_config.py`: public `GET /app-config?version=&platform=` (single object, no envelope); 404 `APP_CONFIG_MISSING` when the doc is absent; when `version` is given, `forceUpdate` is computed server-side from numeric version tuples, otherwise the stored value is echoed.
- `backend/scripts/seed_app_config.py`: seeds `app_config/current` via `set_doc`.
- Tests (`tests/test_app_config.py`): shape, force-update computation (0.9.0 → true, 1.2.0 → false), public access, plus a missing-doc 404 test — all pass with an in-memory patch of `get_doc`.
- Verified live: `curl "http://localhost:8000/v1/app-config?version=0.9.0&platform=android"` — logic verified by tests; live response 500s until Firestore credentials exist (see Blockers).

### Task A4 — Sentry SDK wiring — DONE

- `sentry-sdk[fastapi]>=2.14` added; `SENTRY_DSN=` in `.env.example` with a pointer to the Sentry project settings.
- `main.py` initializes Sentry with `FastApiIntegration`, `traces_sample_rate=0.2`, `environment=settings.env` — silently skipped when DSN is empty (all tests pass with no DSN).
- Dev-only probe `GET /v1/debug/sentry-test` raises `RuntimeError("sentry smoke test")` in `env=dev`, else 404. Verified: returns 500 with empty DSN; will be captured by Sentry once a real DSN is set (manual console check pending — no DSN available in this environment).

### Test run (final)

```
$ cd backend && .venv/bin/pytest -v
tests/test_app_config.py::test_app_config_shape PASSED
tests/test_app_config.py::test_force_update_computed PASSED
tests/test_app_config.py::test_app_config_public PASSED
tests/test_app_config.py::test_app_config_missing PASSED
tests/test_infra.py::test_settings_load PASSED
tests/test_infra.py::test_health PASSED
tests/test_infra.py::test_cache_roundtrip PASSED
7 passed, 2 warnings in 0.12s
```

Warnings are `on_event` deprecations from FastAPI (startup handler per day-file spec); can move to a lifespan handler later without behavior change.

### Blockers / notes

- **No Docker** in this environment — `infra/docker-compose.yml` was created but not exercised; `docker compose up -d redis` is the documented path where Docker exists (a local Redis was used for tests).
- **No GCP/Firestore credentials** — `scripts/seed_app_config.py` fails with `DefaultCredentialsError` and live `/v1/app-config` returns 500 until Application Default Credentials or `secrets/firebase-service-account.json` are provided. Route logic is fully verified via tests. Rerun the seed script once credentials exist.
- **No real Sentry DSN** — wiring verified structurally (empty DSN boots clean; probe returns 500); the Sentry-console event check is pending a dev DSN.
- **Repo has no `.gitignore` yet** — before committing, add `backend/.env`, `backend/.venv/`, `backend/secrets/`, `__pycache__/` per `docs/overview/02` §1.
- Version parsing treats non-numeric parts as 0 and pads to 3 segments, e.g. `"0.9" → (0, 9, 0)`.

## Done-when checklist (Day 1, backend items)

- [x] `curl -s http://localhost:8000/v1/health` → `{"status":"ok"}` (uvicorn from `backend/.venv`)
- [ ] `docker compose -f infra/docker-compose.yml up -d redis` — not verifiable here (no Docker); local Redis used instead, `redis-cli ping` → `PONG`
- [x] `cd backend && .venv/bin/pytest -v` → 7 passed (≥3)
- [x] `backend/app/core/{config,firebase,db,cache}.py` exist with the specified functions
- [x] `curl -s "http://localhost:8000/v1/app-config?version=0.9.0&platform=android"` — tests green (X12); live 200 pending Firestore credentials
- [ ] Sentry event visible in console (X14) — pending real DSN (manual check)
