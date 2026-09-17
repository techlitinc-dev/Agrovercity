from typing import Literal

from pydantic import BaseModel


class DiaryEntryIn(BaseModel):
    title: str
    category: str
    type: Literal["expense", "income", "farmActivity"]
    amount: float = 0
    date: str
    cropName: str | None = None
    notes: str | None = None


class DiaryEntryOut(DiaryEntryIn):
    id: str


class DiaryEntryCreated(BaseModel):
    entry: DiaryEntryOut
    agriCoinsEarned: int
