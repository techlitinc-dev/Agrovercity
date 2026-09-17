import json

from fastapi import APIRouter, Depends

from app.core.cache import cache_get, cache_set
from app.core.deps import current_user_id
from app.services.weather import fetch_weather

router = APIRouter(tags=["weather"])

WEATHER_TTL_SECONDS = 1800


def _cache_key(lat: float, lng: float) -> str:
    return f"weather:{round(lat, 1)}:{round(lng, 1)}"


@router.get("/weather")
async def get_weather(lat: float, lng: float, uid: str = Depends(current_user_id)):
    key = _cache_key(lat, lng)
    cached = await cache_get(key)
    if cached is not None:
        return json.loads(cached)
    data = await fetch_weather(lat, lng)
    await cache_set(key, json.dumps(data), WEATHER_TTL_SECONDS)
    return data
