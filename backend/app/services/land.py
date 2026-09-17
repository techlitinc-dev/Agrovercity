import math
from datetime import datetime

from fastapi import HTTPException

from app.core.deps import require_profile
from app.services import users as users_service

EARTH_RADIUS_KM = 6371.0


def plots_path(uid: str) -> str:
    return f"users/{uid}/land_plots"


def leases_path(uid: str) -> str:
    return f"users/{uid}/land_leases"


def payments_path(uid: str, lease_id: str) -> str:
    return f"users/{uid}/land_leases/{lease_id}/payments"


async def user_or_403(uid: str, *roles) -> dict:
    user = await users_service.get_user(uid)
    require_profile(user, *roles)
    return user


def pending_months(start_date: str, paid_months: set[str]) -> list[str]:
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
    except ValueError:
        return []
    current = datetime.utcnow().date()
    months = []
    y, m = start.year, start.month
    while (y, m) <= (current.year, current.month):
        months.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return [month for month in months if month not in paid_months]


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))
