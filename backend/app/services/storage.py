"""Vault document storage.

Encryption at rest is provided by Cloud Storage (AES-256/GMEK by default) — that
is what the UI's 'AES-256' badge refers to. Never log Aadhaar numbers or file bytes.
"""

import logging
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import firebase_admin

from app.core.config import settings

logger = logging.getLogger(__name__)

# backend/.local_uploads — resolved from this file's location, not the process CWD
LOCAL_UPLOAD_DIR = Path(__file__).resolve().parents[2] / ".local_uploads"


def _dev_mode() -> bool:
    return not firebase_admin._apps


def upload_user_file(uid: str, data: bytes, filename: str, content_type: str, prefix: str = "vault") -> tuple[str, int]:
    blob_path = f"{prefix}/{uid}/{uuid4().hex}_{filename}"
    if _dev_mode():
        LOCAL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        local = LOCAL_UPLOAD_DIR / f"{uuid4().hex}_{filename}"
        local.write_bytes(data)
        logger.warning("Firebase Storage unavailable (dev mode) — wrote %s locally", local)
        return str(local), len(data)
    blob = firebase_admin.storage.bucket().blob(blob_path)
    blob.upload_from_string(data, content_type=content_type)
    return blob_path, len(data)


def signed_download_url(blob_path: str, minutes: int = 60) -> str:
    if _dev_mode():
        return f"file://{blob_path}"
    blob = firebase_admin.storage.bucket().blob(blob_path)
    return blob.generate_signed_url(expiration=timedelta(minutes=minutes), method="GET")


def delete_blob(blob_path: str):
    if _dev_mode():
        p = Path(blob_path)
        if p.exists():
            p.unlink()
        return
    firebase_admin.storage.bucket().blob(blob_path).delete()
