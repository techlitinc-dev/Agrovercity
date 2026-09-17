from typing import Literal

from pydantic import BaseModel, Field


class PlotIn(BaseModel):
    name: str
    village: str
    district: str
    areaAcres: float = Field(gt=0)
    gatNumber: str | None = None
    soilType: str | None = None


class PlotOut(PlotIn):
    id: str
    status: Literal["vacant", "leased"]


class LeaseIn(BaseModel):
    plotId: str
    tenantName: str
    tenantPhone: str
    monthlyRentRupees: float = Field(gt=0)
    startDate: str
    endDate: str


class LeaseOut(LeaseIn):
    id: str
    status: Literal["active", "ended"]
    verified: bool = False


class LeaseUpdateRequest(BaseModel):
    monthlyRentRupees: float | None = None
    endDate: str | None = None
    status: Literal["active", "ended"] | None = None
    verified: bool | None = None


class RentPaymentIn(BaseModel):
    amountRupees: float = Field(gt=0)
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    method: Literal["cash", "upi", "bank"]
    paidAt: str


class RentPaymentOut(RentPaymentIn):
    id: str
    leaseId: str


class LandListingIn(BaseModel):
    village: str
    district: str
    lat: float
    lng: float
    areaAcres: float = Field(gt=0)
    expectedRentRupees: float = Field(gt=0)
    soilType: str | None = None
    waterSource: str | None = None
    plotId: str | None = None


class LandListingOut(LandListingIn):
    id: str
    landlordId: str
    landlordName: str
    status: Literal["open", "leased", "closed"]
    createdAt: str


class LeaseRequestIn(BaseModel):
    listingId: str
    message: str = ""
    durationMonths: int = Field(ge=1, le=120)


class LeaseRequestOut(LeaseRequestIn):
    id: str
    farmerId: str
    farmerName: str
    farmerPhone: str
    landlordId: str
    status: Literal["pending", "accepted", "rejected"]
    createdAt: str


class RejectLeaseRequestIn(BaseModel):
    reason: str = ""
