from fastapi import APIRouter, Depends

from app.core.deps import require_roles

router = APIRouter(prefix="/climate", tags=["climate"])

PRACTICES = ["biochar", "zero-till", "green-manure"]

VARIETIES = [
    {"variety": "Swarna Sub-1", "crop": "Rice", "trait": "flood-tolerant", "source": "IRRI"},
    {"variety": "HHB-67", "crop": "Bajra", "trait": "heat-tolerant", "source": "ICRISAT"},
    {"variety": "Shriram-303", "crop": "Cotton", "trait": "drought-tolerant", "source": "State seed board"},
    {"variety": "ICCV-10", "crop": "Gram", "trait": "wilt-resistant", "source": "ICRISAT"},
    {"variety": "Gujarat Onion-2", "crop": "Onion", "trait": "heat-tolerant", "source": "DOGR"},
    {"variety": "HD-2967", "crop": "Wheat", "trait": "rust-resistant", "source": "IARI"},
]


@router.get("/carbon-potential")
async def carbon_potential(lat: float | None = None, lng: float | None = None, user: dict = Depends(require_roles("farmer"))):
    acres = user.get("landAreaAcres", 0)
    co2e_tonnes = round(acres * 0.92, 1)
    return {
        "co2eTonnes": co2e_tonnes,
        "annualIncomePotential": round(co2e_tonnes * 2000),
        "practices": PRACTICES,
    }


@router.get("/resilient-varieties")
async def resilient_varieties(crop: str | None = None, district: str | None = None, user: dict = Depends(require_roles("farmer"))):
    items = VARIETIES
    if crop:
        items = [v for v in items if crop.lower() in v["crop"].lower()]
    return {"data": items, "page": 1, "pageSize": 50, "total": len(items)}
