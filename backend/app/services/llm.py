import logging
from datetime import date, timedelta

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMUnavailable(Exception):
    pass


def build_system_prompt(user: dict) -> str:
    base = "तुम किसान मित्र हो, भारतीय किसानों के लिए कृषि सहायक। संक्षिप्त, व्यावहारिक उत्तर दो।"
    context = (
        f"किसान: {user.get('name') or 'अनजान'}, गांव: {user.get('village') or '-'}, "
        f"जिला: {user.get('district') or '-'}, क्षेत्र: {user.get('landAreaAcres') or 0} एकड़, "
        f"फसलें: {', '.join(user.get('activeCrops') or []) or '-'}, "
        f"मिट्टी: {user.get('soilType') or '-'}, सिंचाई: {user.get('irrigationType') or '-'}."
    )
    rule = "कभी भी मंडी भाव न बनाएं — लाइव भाव के लिए उपयोगकर्ता को मंडी मॉड्यूल पर भेजें।"
    return f"{base}\n{context}\n{rule}"


async def complete(messages: list[dict]) -> str:
    if not settings.openrouter_api_key:
        last_user = next((m for m in reversed(messages) if m.get("role") == "user"), {})
        return f"यह डेव मोड उत्तर है। आपने पूछा: {last_user.get('content', '')}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
                json={
                    "model": "meta-llama/llama-3.1-8b-instruct",
                    "messages": messages,
                    "max_tokens": 400,
                    "temperature": 0.4,
                },
            )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception:
        logger.warning("LLM completion failed", exc_info=True)
        raise LLMUnavailable("LLM provider unavailable")


async def sarvam_stt(audio_url: str, language: str) -> str:
    result = await speech_stt_for_url(audio_url, language)
    return result["text"]


async def speech_stt_for_url(audio_url: str, language: str) -> dict:
    from app.services import speech

    if not settings.sarvam_api_key:
        return await speech.stt(b"", "audio/mp4", language)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(audio_url)
        resp.raise_for_status()
    return await speech.stt(resp.content, resp.headers.get("content-type", "audio/mp4"), language)


def detect_rich_card(user_message: str) -> tuple[str | None, dict | None]:
    text = user_message.lower()
    if "बुवाई" in user_message or "saturation" in text:
        return (
            "saturation",
            {
                "sowingCount": 24,
                "radiusKm": 10,
                "expectedArrivalIncrease": "18%",
                "riskLevel": "yellow",
                "predictedPrice": 1320,
                "predictedDate": (date.today() + timedelta(days=90)).isoformat(),
                "alternativeCrops": [{"crop": "Soybean", "expectedPrice": 4800}],
            },
        )
    if "मौसम" in user_message or "weather" in text:
        return ("weather", {"tempC": 32, "rainProbability": 20, "condition": "sunny"})
    if "भाव" in user_message or "mandi" in text:
        return ("mandi", {"crop": "Onion", "modalPrice": 1450, "mandiName": "Nashik APMC"})
    if "कीट" in user_message or "pest" in text:
        return ("pest", {"disease": "Pink bollworm", "distanceKm": 3.2, "riskLevel": "yellow"})
    return None, None


def quick_replies_for(card_type: str | None) -> list[str]:
    if card_type == "weather":
        return ["कल बारिश होगी?", "छिड़काव कब करें?"]
    if card_type == "mandi":
        return ["गेहूं का भाव?", "नज़दीकी मंडी?"]
    return ["मौसम बताओ", "आज का भाव?"]
