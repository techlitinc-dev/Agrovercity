from typing import Literal

from pydantic import BaseModel, Field


class GaushalaItem(BaseModel):
    id: str
    name: str
    trustName: str
    address: str
    district: str
    distanceKm: float
    cowCount: int
    breeds: list[str]
    phone: str
    providesOrganicManure: bool
    offersCowAdoption: bool
    rating: float
    facilities: list[str]


class ManureOrderIn(BaseModel):
    product: str
    quantity: str


class PlantNursery(BaseModel):
    id: str
    name: str
    address: str
    district: str
    distanceKm: float
    phone: str
    saplingsAvailable: list[str]
    isGovtCertified: bool
    rating: float


class VetDoctor(BaseModel):
    id: str
    name: str
    clinicName: str
    address: str
    district: str
    distanceKm: float
    phone: str
    specialization: str
    consultationFeeRupees: float
    availableForFarmVisit: bool
    emergencyAvailable: bool
    nextAvailableSlot: str
    rating: float


class VetBookIn(BaseModel):
    visitType: Literal["farm", "clinic"]
    slot: str
    animalType: str


class DairyProductItem(BaseModel):
    id: str
    name: str
    category: str
    description: str
    priceRupees: float
    unit: str
    inStock: bool
    purityCertification: str
    rating: float


class DairyOrderIn(BaseModel):
    quantity: int = Field(ge=1)
