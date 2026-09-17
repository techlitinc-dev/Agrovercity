from pydantic import BaseModel


class ContractOut(BaseModel):
    id: str
    buyerCompany: str
    buyerRating: float
    crop: str
    lockedRateQuintal: float
    mspCurrentRate: float
    premiumAboveMSP: float
    minQuantityQuintals: float
    deliveryLocation: str
    paymentTerms: str
    status: str
    contractDuration: str


class AcceptContractRequest(BaseModel):
    signatureData: str
    consentTimestamp: str
    mpin: str
