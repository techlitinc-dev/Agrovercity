# Backend Summary

Status tracker for Dev A (backend) work, day by day.

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
