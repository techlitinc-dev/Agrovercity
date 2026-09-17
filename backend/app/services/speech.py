"""Speech services: Sarvam STT + Bhashini TTS stub."""

import httpx

from app.core.config import settings
from app.services import storage as storage_service


class SpeechUnavailable(Exception):
    pass


async def stt(audio_bytes: bytes, content_type: str, language_hint: str | None = None) -> dict:
    if not settings.sarvam_api_key:
        return {"text": "आज प्याज का भाव क्या है?", "language": "hi"}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.sarvam.ai/speech-to-text",
                files={"file": ("audio.m4a", audio_bytes, content_type)},
                data={"model": "saarika", "language_code": language_hint or "hi"},
            )
        resp.raise_for_status()
        payload = resp.json()
        return {"text": payload.get("transcript", ""), "language": payload.get("language_code", language_hint or "hi")}
    except Exception:
        raise SpeechUnavailable("Speech-to-text provider unavailable")


async def tts(text: str, language: str, uid: str | None = None) -> str:
    if not settings.sarvam_api_key:
        return "https://example.com/tts-sample.mp3"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.sarvam.ai/text-to-speech",
                json={"text": text, "target_language_code": language},
            )
        resp.raise_for_status()
        import base64

        audio = base64.b64decode(resp.json().get("audios", [""])[0])
        blob_path, _ = storage_service.upload_user_file(uid or "system", audio, "tts.wav", "audio/wav", prefix="tts")
        return storage_service.signed_download_url(blob_path)
    except Exception:
        raise SpeechUnavailable("Text-to-speech provider unavailable")
