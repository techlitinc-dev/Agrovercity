"""FCM send + notification store.

Day 13 formalisation: `notify(uid, title, body, data)` writes the in-app
notification doc then fans out to the user's registered devices. Dev mode
(no Firebase) is log-only. Never raises into routers.
"""

import logging
from datetime import datetime, timezone
from uuid import uuid4

import firebase_admin

from app.core import db

logger = logging.getLogger(__name__)


async def send_to_user(uid: str, title: str, body: str, data: dict = {}) -> int:
    devices = await db.list_subdocs(f"users/{uid}/devices")
    if not devices:
        return 0
    tokens = [d.get("fcmToken") for d in devices if d.get("fcmToken")]
    if not tokens:
        return 0
    if not firebase_admin._apps:
        logger.info("FCM(dev) to %s: %s (%s) — %s tokens", uid, title, body, len(tokens))
        return 0
    try:
        from firebase_admin import messaging

        message = messaging.MulticastMessage(
            tokens=tokens,
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in data.items()},
        )
        response = messaging.send_each_for_multicast(message)
        success = sum(1 for r in response.responses if r.success)
        for device, result in zip(devices, response.responses):
            if not result.success and isinstance(result.exception, messaging.UnregisteredError):
                await db.delete_subdoc_at(f"users/{uid}/devices", device["id"])
        return success
    except Exception:
        logger.warning("FCM send failed for %s", uid, exc_info=True)
        return 0


async def notify(uid: str, title: str, body: str, data: dict = {}) -> str:
    doc = {
        "id": uuid4().hex,
        "title": title,
        "body": body,
        "type": data.get("type"),
        "read": False,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        **data,
    }
    await db.set_subdoc_at(f"users/{uid}/notifications", doc["id"], doc)
    await send_to_user(uid, title, body, data)
    return doc["id"]
