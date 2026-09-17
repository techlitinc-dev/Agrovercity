from typing import Literal

from pydantic import BaseModel, Field


class SaturationIn(BaseModel):
    crop: str
    district: str
    lat: float
    lng: float
    radiusKm: int = 10
    shareSowingIntent: bool = True


class SaturationOut(BaseModel):
    sowingCount: int
    radiusKm: int
    expectedArrivalIncrease: str
    riskLevel: Literal["green", "yellow", "red"]
    predictedPrice: float
    predictedDate: str
    alternativeCrops: list[dict]


class PestDisease(BaseModel):
    diseaseName: str
    crop: str
    pathogen: str
    confidence: float
    symptoms: str
    chemicalTreatment: str
    organicTreatment: str
    dosage: str
    estimatedCost: float


class NpkIn(BaseModel):
    n: float
    p: float
    k: float
    crop: str
    soilType: str


class NpkOut(BaseModel):
    recommendations: list[str]
    ureaKgPerAcre: float
    dapKgPerAcre: float
    mopKgPerAcre: float
