from typing import Literal

from pydantic import BaseModel


class ChatMessageIn(BaseModel):
    text: str | None = None
    audioUrl: str | None = None
    language: str = "hi"
    sessionId: str


class KisanMitraMessage(BaseModel):
    id: str
    sender: Literal["bot", "user"]
    text: str
    timestamp: str
    quickReplies: list[str] = []
    richCardType: str | None = None
    richCardData: dict | None = None


class HandoffIn(BaseModel):
    sessionId: str
    reason: str


class HandoffOut(BaseModel):
    expertName: str
    contactChannel: str
    etaMinutes: int
