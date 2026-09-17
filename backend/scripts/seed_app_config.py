import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.db import set_doc

APP_CONFIG_DOC = {
    "minSupportedVersion": "1.0.0",
    "forceUpdate": False,
    "featureFlags": {
        "liveChannels": True,
        "bnpl": False,
    },
    "maintenanceMode": False,
}


async def main():
    await set_doc("app_config", "current", APP_CONFIG_DOC)
    print("seeded app_config/current")


if __name__ == "__main__":
    asyncio.run(main())
