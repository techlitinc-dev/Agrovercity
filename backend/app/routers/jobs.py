# Cron-triggered job endpoints. Cloud Scheduler hits these nightly
# (0 22 * * * IST) with the X-Cron-Secret header — scheduler setup belongs to
# docs/deployment/backend-deploy.md.

import logging

from fastapi import APIRouter, Depends, Header, HTTPException

from app.core.config import settings
from app.models.settlements import SettlementRunIn
from app.services.settlements import last_iso_week, run_settlements

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _check_cron_secret(x_cron_secret: str | None):
    if not settings.cron_secret:
        logger.warning("CRON_SECRET not set — allowing job trigger without auth (dev mode)")
        return
    if x_cron_secret != settings.cron_secret:
        raise HTTPException(
            status_code=401,
            detail={"code": "CRON_UNAUTHORIZED", "message": "Invalid cron secret", "fieldErrors": {}},
        )


@router.post("/settlements/run")
async def run_settlements_job(
    body: SettlementRunIn | None = None,
    x_cron_secret: str | None = Header(default=None),
):
    _check_cron_secret(x_cron_secret)
    period_start, period_end = last_iso_week()
    if body is not None:
        period_start = body.periodStart or period_start
        period_end = body.periodEnd or period_end
    summary = await run_settlements(period_start, period_end)
    return {**summary, "periodStart": period_start, "periodEnd": period_end}
