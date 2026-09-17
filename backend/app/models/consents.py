from pydantic import BaseModel


class ConsentsIn(BaseModel):
    dataSharing: bool
    location: bool
    marketing: bool


class ConsentsOut(ConsentsIn):
    updatedAt: str


class ConsentRequiredError(Exception):
    """Raised when dataSharing consent is off; routers map to 403 CONSENT_REQUIRED."""
