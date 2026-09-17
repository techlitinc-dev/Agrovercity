from fastapi import APIRouter

from app.data.district_crops import DISTRICT_CROPS
from app.data.languages import LANGUAGES, REGIONAL_MAPPING
from app.services import geo

router = APIRouter(tags=["reference"])


@router.get("/geo/reverse")
async def reverse_geocode(lat: float, lng: float):
    return geo.adapter.reverse(lat, lng)


@router.get("/regions/crops")
async def region_crops(district: str):
    for entry in DISTRICT_CROPS:
        if entry["district"].lower() == district.lower():
            return entry
    return {"district": district, "kharif": [], "rabi": [], "suggested": []}


@router.get("/languages")
async def languages():
    return {"languages": LANGUAGES, "regionalMapping": REGIONAL_MAPPING}
