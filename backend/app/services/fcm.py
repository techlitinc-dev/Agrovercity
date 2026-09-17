"""Thin FCM notify facade — Day 13 Task A4 formalises this module.

Today it writes the in-app notifications doc (and topic FCM when the admin SDK
is initialised) via the Day 7 notifications service, so callers can depend on
the stable `notify(uid, title, body, data)` signature already.
"""

from app.services.notifications import send_fcm_to_user


async def notify(uid: str, title: str, body: str, data: dict):
    await send_fcm_to_user(uid, title, body, data)
