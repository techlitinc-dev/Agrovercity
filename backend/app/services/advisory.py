from datetime import date, timedelta

from app.core import db
from app.models.advisory import SaturationIn, SaturationOut

BASE_PRICES = {"onion": 1450, "wheat": 2275, "tomato": 1100}
DEFAULT_BASE = 1500
RISK_FACTORS = {"green": 1.0, "yellow": 0.92, "red": 0.80}
DEFAULT_ALTERNATIVES = [{"crop": "Soybean", "expectedPrice": 5040}, {"crop": "Maize", "expectedPrice": 2250}]
ALTERNATIVES = {
    "onion": [{"crop": "Soybean", "expectedPrice": round(4800 * 1.05)}, {"crop": "Gram", "expectedPrice": round(5400 * 1.05)}],
}


def risk_level(count: int) -> str:
    if count < 20:
        return "green"
    if count < 60:
        return "yellow"
    return "red"


async def saturation(inp: SaturationIn, exclude_uid: str | None = None) -> SaturationOut:
    cycles = await db.query("crop_cycles", [("crop", "==", inp.crop), ("district", "==", inp.district)], limit=10000)
    if exclude_uid:
        cycles = [c for c in cycles if not (c.get("userId") == exclude_uid and not c.get("isIntent"))]
    count = len(cycles)
    level = risk_level(count)
    base = BASE_PRICES.get(inp.crop.lower(), DEFAULT_BASE)
    predicted_price = round(base * RISK_FACTORS[level], 2)
    alternatives = ALTERNATIVES.get(inp.crop.lower(), DEFAULT_ALTERNATIVES)
    return SaturationOut(
        sowingCount=count,
        radiusKm=inp.radiusKm,
        expectedArrivalIncrease=f"{count * 8}%",
        riskLevel=level,
        predictedPrice=predicted_price,
        predictedDate=(date.today() + timedelta(days=90)).isoformat(),
        alternativeCrops=alternatives,
    )


def current_season(month: int | None = None) -> str:
    month = month if month is not None else date.today().month
    return "Kharif" if 6 <= month <= 10 else "Rabi"


CROP_TARGETS = {"wheat": (120, 60, 40), "onion": (100, 50, 50), "tomato": (150, 80, 80)}
DEFAULT_TARGET = (100, 50, 50)


def npk_recommendation(n: float, p: float, k: float, crop: str) -> dict:
    target_n, target_p, target_k = CROP_TARGETS.get(crop.lower(), DEFAULT_TARGET)
    deficit_n = max(0.0, target_n - n)
    deficit_p = max(0.0, target_p - p)
    deficit_k = max(0.0, target_k - k)
    urea = round(deficit_n / 0.46 / 2.5, 1)
    dap = round(deficit_p / 0.46 / 2.5, 1)
    mop = round(deficit_k / 0.60 / 2.5, 1)
    recommendations = [
        f"यूरिया: {urea} किग्रा/एकड़ (नाइट्रोजन की कमी के लिए)",
        f"DAP: {dap} किग्रा/एकड़ (फास्फोरस की कमी के लिए)",
        f"MOP: {mop} किग्रा/एकड़ (पोटैश की कमी के लिए)",
    ]
    return {"ureaKgPerAcre": urea, "dapKgPerAcre": dap, "mopKgPerAcre": mop, "recommendations": recommendations}
