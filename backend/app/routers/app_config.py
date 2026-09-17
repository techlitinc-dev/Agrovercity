import re

from fastapi import APIRouter, HTTPException

from app.core.db import get_doc
from app.models.app_config import AppConfigOut

router = APIRouter(tags=["app-config"])

APP_CONFIG_COLLECTION = "app_config"
APP_CONFIG_DOC = "current"


def _version_tuple(version: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", version)
    if not parts:
        return (0, 0, 0)
    nums = [int(p) for p in parts]
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums[:3])


@router.get("/app-config")
async def get_app_config(version: str | None = None, platform: str | None = None) -> AppConfigOut:
    doc = await get_doc(APP_CONFIG_COLLECTION, APP_CONFIG_DOC)
    if doc is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "APP_CONFIG_MISSING", "message": "App config not found", "fieldErrors": {}},
        )
    force_update = doc["forceUpdate"]
    if version is not None:
        force_update = _version_tuple(version) < _version_tuple(doc["minSupportedVersion"])
    return AppConfigOut(
        minSupportedVersion=doc["minSupportedVersion"],
        forceUpdate=force_update,
        featureFlags=doc.get("featureFlags", {}),
        maintenanceMode=doc.get("maintenanceMode", False),
    )
