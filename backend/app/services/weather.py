import httpx

from app.core.config import settings

DEV_FIXTURE = {
    "tempC": 31,
    "rainProbability": 40,
    "condition": "Partly Cloudy",
    "radarAvailable": True,
    "forecast": [
        {"day": "Today", "tempC": 31, "rainProbability": 40},
        {"day": "Tomorrow", "tempC": 30, "rainProbability": 55},
    ],
}


def _map_openweather(payload: dict) -> dict:
    current = payload.get("main", {})
    weather = payload.get("weather", [{}])[0]
    return {
        "tempC": round(current.get("temp", 0)),
        "rainProbability": payload.get("clouds", {}).get("all", 0),
        "condition": weather.get("main", "Unknown"),
        "radarAvailable": False,
        "forecast": [],
    }


async def fetch_weather(lat: float, lng: float) -> dict:
    if not settings.weather_api_key:
        return DEV_FIXTURE
    url = "https://api.openweathermap.org/data/2.5/weather"
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            url,
            params={"lat": lat, "lng": lng, "appid": settings.weather_api_key, "units": "metric"},
        )
        resp.raise_for_status()
        return _map_openweather(resp.json())
