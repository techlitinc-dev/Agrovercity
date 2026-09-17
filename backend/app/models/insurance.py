from typing import Literal

from pydantic import BaseModel, Field


class CropInsurancePolicy(BaseModel):
    id: str
    policyNumber: str
    schemeName: str
    cropName: str
    season: str
    year: int
    landAreaAcres: float
    sumInsured: float
    farmerPremium: float
    govtSubsidy: float
    status: str
    insuranceCompany: str
    coverageStartDate: str
    coverageEndDate: str
    bankName: str
    kccAccountNo: str
    certificateUrl: str | None = None


class PolicyApplyIn(BaseModel):
    cropName: str
    season: Literal["Kharif", "Rabi", "Annual"]
    landAreaAcres: float = Field(gt=0)


class CropPremiumRate(BaseModel):
    id: str
    cropName: str
    category: str
    season: str
    sumInsuredPerAcre: float
    farmerSharePercent: float
    totalActuarialRatePercent: float
    cutoffDate: str
