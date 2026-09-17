from datetime import datetime, timedelta, timezone

from app.core import db


def _ts(minutes_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()


NEWS = [
    {
        "id": "news-1",
        "title": "MSP hiked for wheat and gram",
        "vernacularTitle": "गेहूं और चने के MSP में बढ़ोतरी",
        "category": "market-policy",
        "source": "PIB",
        "timestamp": _ts(30),
        "summary": "Cabinet approves higher MSP for Rabi marketing season.",
        "content": "The cabinet has approved a higher minimum support price for wheat and gram for the coming Rabi marketing season, benefiting growers across the state.",
        "isBreaking": True,
        "audioText": "केंद्र सरकार ने गेहूं और चने का न्यूनतम समर्थन मूल्य बढ़ाया है।",
        "impactRating": 4.5,
    },
    {
        "id": "news-2",
        "title": "Heavy rain alert for Nashik district",
        "vernacularTitle": "नाशिक जिले में भारी बारिश का अलर्ट",
        "category": "weather-alert",
        "source": "IMD",
        "timestamp": _ts(90),
        "summary": "IMD issues a 48-hour heavy rainfall warning.",
        "content": "The meteorological department has issued a heavy rainfall alert for Nashik district for the next 48 hours. Farmers are advised to postpone spraying.",
        "isBreaking": False,
        "audioText": "मौसम विभाग ने नाशिक जिले में भारी बारिश का अलर्ट जारी किया है।",
        "impactRating": 4.0,
    },
    {
        "id": "news-3",
        "title": "Drip subsidy applications open",
        "vernacularTitle": "ड्रिप सब्सिडी के आवेदन शुरू",
        "category": "govt-subsidy",
        "source": "Mahadbt",
        "timestamp": _ts(240),
        "summary": "PMKSY drip subsidy window opens on Mahadbt portal.",
        "content": "Farmers can now apply for the 55 percent drip irrigation subsidy through the Mahadbt portal until the end of the month.",
        "isBreaking": False,
        "audioText": "ड्रिप सिंचाई सब्सिडी के लिए आवेदन शुरू हो गए हैं।",
        "impactRating": 3.5,
    },
    {
        "id": "news-4",
        "title": "Drone spraying pilot expands",
        "vernacularTitle": "ड्रोन छिड़काव पायलट विस्तारित",
        "category": "agri-tech",
        "source": "AgriToday",
        "timestamp": _ts(600),
        "summary": "KVK drone-spraying pilot adds 12 more villages.",
        "content": "The KVK-led drone spraying pilot will now cover twelve additional villages this season at a subsidised rate per acre.",
        "isBreaking": False,
        "audioText": "केवीके का ड्रोन छिड़काव पायलट अब और गांवों तक फैलेगा।",
        "impactRating": 3.0,
    },
    {
        "id": "news-5",
        "title": "Onion arrivals rise at Lasalgaon",
        "vernacularTitle": "लासलगांव में प्याज की आवक बढ़ी",
        "category": "market-policy",
        "source": "Lasalgaon APMC",
        "timestamp": _ts(900),
        "summary": "Higher arrivals push onion prices down 3 percent.",
        "content": "Onion arrivals at Lasalgaon APMC rose this week, pulling modal prices down by around 3 percent.",
        "isBreaking": False,
        "audioText": "लासलगांव मंडी में प्याज की आवक बढ़ने से भाव गिरे हैं।",
        "impactRating": 3.5,
    },
    {
        "id": "news-6",
        "title": "Soil health card camps announced",
        "vernacularTitle": "मृदा स्वास्थ्य कार्ड शिविर की घोषणा",
        "category": "govt-subsidy",
        "source": " Agriculture Dept",
        "timestamp": _ts(1440),
        "summary": "Free soil-testing camps in 20 villages this month.",
        "content": "The agriculture department will run free soil-testing camps across twenty villages this month.",
        "isBreaking": False,
        "audioText": "इस महीने 20 गांवों में मुफ्त मिट्टी परीक्षण शिविर लगेंगे।",
        "impactRating": 3.0,
    },
]

STREAM_URL = "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8"

CHANNELS = [
    {
        "id": "ch-1",
        "channelName": "DD Kisan",
        "broadcaster": "Prasar Bharati",
        "programTitle": "Krishi Darshan",
        "currentSpeaker": "Dr. S. Deshmukh",
        "liveViewersCount": 1200,
        "isLiveNow": True,
        "category": "govt",
        "streamThumbnail": "https://example.com/thumb-ddkisan.jpg",
        "streamUrl": STREAM_URL,
        "scheduleTime": "06:00-22:00",
    },
    {
        "id": "ch-2",
        "channelName": "KVK Live",
        "broadcaster": "KVK Nashik",
        "programTitle": "Ask the Scientist",
        "currentSpeaker": "Dr. Meena Jadhav",
        "liveViewersCount": 340,
        "isLiveNow": True,
        "category": "advisory",
        "streamThumbnail": "https://example.com/thumb-kvk.jpg",
        "streamUrl": STREAM_URL,
        "scheduleTime": "17:00-19:00",
    },
    {
        "id": "ch-3",
        "channelName": "Nashik APMC Auction",
        "broadcaster": "Nashik APMC",
        "programTitle": "Live Onion Auction",
        "currentSpeaker": "Auctioneer",
        "liveViewersCount": 210,
        "isLiveNow": False,
        "category": "market",
        "streamThumbnail": "https://example.com/thumb-apmc.jpg",
        "streamUrl": STREAM_URL,
        "scheduleTime": "08:00-12:00",
    },
    {
        "id": "ch-4",
        "channelName": "Maharashtra Agri TV",
        "broadcaster": "MATV",
        "programTitle": "Shetkari Chat",
        "currentSpeaker": "Panel discussion",
        "liveViewersCount": 95,
        "isLiveNow": False,
        "category": "advisory",
        "streamThumbnail": "https://example.com/thumb-matv.jpg",
        "streamUrl": STREAM_URL,
        "scheduleTime": "19:00-21:00",
    },
]


async def seed_content():
    if await db.query("news", [], limit=1):
        return
    for doc in NEWS:
        await db.set_doc("news", doc["id"], doc)
    for doc in CHANNELS:
        await db.set_doc("channels", doc["id"], doc)
