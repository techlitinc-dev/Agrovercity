import logging
from pathlib import Path

import firebase_admin
from firebase_admin import credentials

from app.core.config import settings

logger = logging.getLogger(__name__)


def init_firebase():
    if firebase_admin._apps:
        return
    path = Path(settings.firebase_service_account_path)
    if not path.exists():
        logger.warning(
            "Firebase service account not found at %s — skipping init (dev mode)",
            path,
        )
        return
    cred = credentials.Certificate(str(path))
    firebase_admin.initialize_app(cred, {"projectId": settings.firebase_project_id})
