from typing import Literal

from pydantic import BaseModel, Field


class ClaimTimelineEntry(BaseModel):
    status: str
    at: str
    note: str


class InsuranceClaimRecord(BaseModel):
    id: str
    claimNumber: str
    policyId: str
    cropName: str
    calamityType: str
    dateOfDamage: str
    cropStage: str
    estimatedLossPercent: float
    requestedAmount: float
    approvedAmount: float | None
    status: str
    statusText: str
    surveyorName: str | None
    surveyorPhone: str | None
    surveyorVisitDate: str | None
    gpsCoordinates: str
    village: str
    damagePhotos: list[str]
    submittedAt: str
    dbtTransactionId: str | None
    bankAccountLast4: str | None
    timeline: list[ClaimTimelineEntry]
    appealCount: int = 0
    rejectionReason: str | None = None


class AppealIn(BaseModel):
    reason: str = Field(min_length=10, max_length=1000)
    photos: list[str] = []
