"""SMS sender — MSG91-backed with a dev-mode log-only default.

Templates must be DLT-registered (India TRAI rule); template IDs live in
app/core/config.py settings.
"""

import logging
from typing import Protocol

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class SmsSender(Protocol):
    async def send(self, phone: str, template_id: str, params: dict) -> bool: ...


class Msg91Sender:
    async def send(self, phone: str, template_id: str, params: dict) -> bool:
        resp = httpx.post(
            "https://control.msg91.com/api/v5/flow/",
            headers={"authkey": settings.msg91_auth_key},
            json={"template_id": template_id, "recipients": [{"mobiles": phone.lstrip("+"), **params}]},
        )
        return resp.status_code == 200


class LogOnlySender:
    async def send(self, phone: str, template_id: str, params: dict) -> bool:
        logger.info("SMS(dev) to %s template=%s params=%s", phone, template_id, params)
        return True


def get_sms_sender() -> SmsSender:
    if settings.msg91_auth_key:
        return Msg91Sender()
    return LogOnlySender()


async def send_invite(phone: str, code: str) -> bool:
    return await get_sms_sender().send(phone, settings.sms_template_invite, {"code": code})
