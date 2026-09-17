from typing import Literal

from pydantic import BaseModel


class GamificationStatus(BaseModel):
    krishiRatnaLevel: int
    krishiRatnaTitle: str
    agriCoins: int
    streakDays: int
    xpToNextLevel: int


class Reward(BaseModel):
    id: str
    title: str
    coinCost: int
    type: Literal["voucher", "service", "discount"]


class RedeemIn(BaseModel):
    rewardId: str


class LedgerEntry(BaseModel):
    id: str
    amount: int
    reason: str
    refId: str | None
    at: str
