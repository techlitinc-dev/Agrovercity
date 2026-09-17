import logging

import sentry_sdk
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration

from app.core.config import settings
from app.core.firebase import init_firebase
from app.routers import app_config, auth, health, reference, users, weather

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        integrations=[FastApiIntegration()],
        traces_sample_rate=0.2,
        environment=settings.env,
    )

app = FastAPI(title="AGROVERCITY API", version="0.1.0")
app.include_router(health.router, prefix="/v1")
app.include_router(app_config.router, prefix="/v1")
app.include_router(auth.router, prefix="/v1")
app.include_router(users.router, prefix="/v1")
app.include_router(reference.router, prefix="/v1")
app.include_router(weather.router, prefix="/v1")


@app.exception_handler(HTTPException)
async def error_envelope_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if not isinstance(detail, dict):
        detail = {"code": "ERROR", "message": str(detail), "fieldErrors": {}}
    return JSONResponse(status_code=exc.status_code, content={"error": detail}, headers=exc.headers)


@app.on_event("startup")
async def startup():
    init_firebase()


@app.get("/v1/debug/sentry-test")
async def sentry_test():
    if settings.env != "dev":
        raise HTTPException(status_code=404)
    raise RuntimeError("sentry smoke test")
