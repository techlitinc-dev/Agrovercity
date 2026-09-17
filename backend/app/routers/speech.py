from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.deps import current_user_id
from app.services import speech as speech_service
from app.services.speech import SpeechUnavailable

router = APIRouter(prefix="/speech", tags=["speech"])

ALLOWED_AUDIO = {"audio/mp4", "audio/x-m4a", "audio/wav", "audio/x-wav"}
MAX_SIZE_BYTES = 5 * 1024 * 1024  # ≈ 60 s of m4a at typical bitrates — duration cap enforced by size


def _speech_unavailable():
    return HTTPException(
        status_code=503,
        detail={"code": "SPEECH_UNAVAILABLE", "message": "आवाज़ सेवा उपलब्ध नहीं है", "fieldErrors": {}},
    )


@router.post("/stt")
async def stt(file: UploadFile = File(...), languageHint: str | None = Form(default=None), uid: str = Depends(current_user_id)):
    if file.content_type not in ALLOWED_AUDIO:
        return JSONResponse(
            status_code=415,
            content={"error": {"code": "UNSUPPORTED_FILE_TYPE", "message": "Only m4a/wav audio is accepted", "fieldErrors": {}}},
        )
    data = await file.read()
    if len(data) > MAX_SIZE_BYTES:
        return JSONResponse(
            status_code=413,
            content={"error": {"code": "FILE_TOO_LARGE", "message": "Audio exceeds the 5 MB limit", "fieldErrors": {}}},
        )
    try:
        return await speech_service.stt(data, file.content_type, languageHint)
    except SpeechUnavailable:
        raise _speech_unavailable()


class TtsIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    language: str = "hi"


@router.post("/tts")
async def tts(body: TtsIn, uid: str = Depends(current_user_id)):
    try:
        audio_url = await speech_service.tts(body.text, body.language, uid)
    except SpeechUnavailable:
        raise _speech_unavailable()
    return {"audioUrl": audio_url}
