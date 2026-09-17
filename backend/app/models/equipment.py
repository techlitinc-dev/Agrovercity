from pydantic import BaseModel


class EquipmentOut(BaseModel):
    id: str
    name: str
    type: str
    ownerType: str
    hourlyRate: float
    perAcreRate: float | None
    distanceKm: float


class SlotOut(BaseModel):
    id: str
    equipmentId: str
    date: str
    slotName: str
    duration: str
    status: str
    bookedByName: str | None
    priceRupees: float
    recommendedTask: str


class EquipmentUpsertRequest(BaseModel):
    name: str
    type: str
    ownerType: str = "private"
    hourlyRate: float
    perAcreRate: float | None = None
    slotTemplate: list[dict] | None = None
    rcDocUrl: str | None = None
    insuranceDocUrl: str | None = None


class BookSlotRequest(BaseModel):
    farmerName: str


class JoinPoolRequest(BaseModel):
    units: int


class RejectEquipmentBookingRequest(BaseModel):
    reason: str
