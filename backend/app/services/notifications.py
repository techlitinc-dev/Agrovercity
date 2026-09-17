from datetime import datetime, timezone
from uuid import uuid4

import firebase_admin

from app.core import db


async def send_fcm_to_user(uid: str, title: str, body: str, data: dict):
    # Token-based FCM registration lands Day 13 — meanwhile fan out to topic user_{uid}
    # only when the admin SDK is initialised, and ALWAYS write the in-app inbox doc.
    if firebase_admin._apps:
        try:
            from firebase_admin import messaging

            messaging.send(
                messaging.Message(
                    notification=messaging.Notification(title=title, body=body),
                    data={k: str(v) for k, v in data.items()},
                    topic=f"user_{uid}",
                )
            )
        except Exception:
            pass
    await db.set_doc(
        "notifications",
        f"notif_{uuid4().hex[:10]}",
        {
            "userId": uid,
            "title": title,
            "body": body,
            "data": data,
            "read": False,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        },
    )
