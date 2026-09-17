import logging

import sentry_sdk
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration

from app.core.config import settings
from app.core.firebase import init_firebase
from app.routers import (
    addresses,
    admin,
    app_config,
    auth,
    advisory,
    bank_accounts,
    chatbot,
    climate,
    contracts,
    content,
    diary,
    equipment,
    equipment_owner,
    finance,
    fpo,
    gamification,
    gyan,
    health,
    insurance,
    jobs,
    land,
    land_market,
    land_records,
    livestock,
    lots,
    mandi,
    marketplace,
    notifications,
    orders,
    pnl,
    post_harvest,
    ratings,
    referrals,
    reference,
    schemes,
    seller,
    settlements,
    soil_tests,
    speech,
    support,
    sync,
    transport,
    tree,
    users,
    users_blocks,
    vault,
    water,
    weather,
    women,
)
from app.routers.users import devices_router

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
app.include_router(mandi.router, prefix="/v1")
app.include_router(seller.router, prefix="/v1")
app.include_router(lots.router, prefix="/v1")
app.include_router(marketplace.router, prefix="/v1")
app.include_router(orders.router, prefix="/v1")
app.include_router(addresses.router, prefix="/v1")
app.include_router(contracts.router, prefix="/v1")
app.include_router(transport.router, prefix="/v1")
app.include_router(equipment.router, prefix="/v1")
app.include_router(equipment_owner.router, prefix="/v1")
app.include_router(fpo.router, prefix="/v1")
app.include_router(diary.router, prefix="/v1")
app.include_router(pnl.router, prefix="/v1")
app.include_router(finance.router, prefix="/v1")
app.include_router(land.router, prefix="/v1")
app.include_router(land_market.router, prefix="/v1")
app.include_router(bank_accounts.router, prefix="/v1")
app.include_router(insurance.router, prefix="/v1")
app.include_router(settlements.router, prefix="/v1")
app.include_router(jobs.router, prefix="/v1")
app.include_router(schemes.router, prefix="/v1")
app.include_router(vault.router, prefix="/v1")
app.include_router(land_records.router, prefix="/v1")
app.include_router(water.router, prefix="/v1")
app.include_router(soil_tests.router, prefix="/v1")
app.include_router(devices_router, prefix="/v1")
app.include_router(content.router, prefix="/v1")
app.include_router(gyan.router, prefix="/v1")
app.include_router(livestock.router, prefix="/v1")
app.include_router(tree.router, prefix="/v1")
app.include_router(ratings.router, prefix="/v1")
app.include_router(chatbot.router, prefix="/v1")
app.include_router(advisory.router, prefix="/v1")
app.include_router(gamification.router, prefix="/v1")
app.include_router(referrals.router, prefix="/v1")
app.include_router(notifications.router, prefix="/v1")
app.include_router(support.router, prefix="/v1")
app.include_router(speech.router, prefix="/v1")
app.include_router(sync.router, prefix="/v1")
app.include_router(women.router, prefix="/v1")
app.include_router(climate.router, prefix="/v1")
app.include_router(post_harvest.router, prefix="/v1")
app.include_router(users_blocks.router, prefix="/v1")
app.include_router(admin.router, prefix="/v1")

# middleware: last-added runs outermost — logging must see rate-limit 429s
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.logging import LoggingMiddleware

app.add_middleware(RateLimitMiddleware)
app.add_middleware(LoggingMiddleware)


@app.exception_handler(HTTPException)
async def error_envelope_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if not isinstance(detail, dict):
        detail = {"code": "ERROR", "message": str(detail), "fieldErrors": {}}
    return JSONResponse(status_code=exc.status_code, content={"error": detail}, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_envelope_handler(request: Request, exc: RequestValidationError):
    field_errors = {}
    for err in exc.errors():
        loc = ".".join(str(part) for part in err["loc"][1:])
        field_errors[loc] = err["msg"]
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "VALIDATION_ERROR", "message": "Validation failed", "fieldErrors": field_errors}},
    )


@app.exception_handler(Exception)
async def internal_error_handler(request: Request, exc: Exception):
    import logging

    logging.getLogger(__name__).error(
        "Unhandled error on %s %s", request.method, request.url.path, exc_info=exc
    )
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "Something went wrong", "fieldErrors": {}}},
    )


from app.services.coins import InsufficientCoins


@app.exception_handler(InsufficientCoins)
async def insufficient_coins_handler(request: Request, exc: InsufficientCoins):
    return JSONResponse(
        status_code=409,
        content={"error": {"code": "INSUFFICIENT_COINS", "message": "पर्याप्त कॉइन नहीं", "fieldErrors": {}}},
    )


@app.on_event("startup")
async def startup():
    init_firebase()
    try:
        from app.data.gyan_seed import seed_gyan
        from app.data.rewards_seed import seed_rewards
        from app.data.insurance_seed import seed_insurance_rates
        from app.data.livestock_seed import seed_livestock
        from app.data.schemes_seed import seed_schemes
        from app.data.tree_seed import seed_tree
        from app.data.content_seed import seed_content

        await seed_schemes()
        await seed_insurance_rates()
        await seed_content()
        await seed_gyan()
        await seed_livestock()
        await seed_tree()
        await seed_rewards()
    except Exception:
        logging.getLogger(__name__).warning("Scheme seeding skipped (Firestore unavailable)")


@app.get("/v1/debug/sentry-test")
async def sentry_test():
    if settings.env != "dev":
        raise HTTPException(status_code=404)
    raise RuntimeError("sentry smoke test")
