from pydantic import BaseModel, Field


class AgriNewsItem(BaseModel):
    id: str
    title: str
    vernacularTitle: str
    category: str
    source: str
    timestamp: str
    summary: str
    content: str
    isBreaking: bool
    audioText: str
    impactRating: float


class AgriLiveChannel(BaseModel):
    id: str
    channelName: str
    broadcaster: str
    programTitle: str
    currentSpeaker: str
    liveViewersCount: int
    isLiveNow: bool
    category: str
    streamThumbnail: str
    streamUrl: str
    scheduleTime: str


class ChatMessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=300)


class ChatMessageOut(BaseModel):
    id: str
    userName: str
    text: str
    sentAt: str
