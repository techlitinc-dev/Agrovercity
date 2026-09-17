import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import firebase_admin
from firebase_admin import auth as firebase_auth


async def main(uid: str):
    firebase_admin.initialize_app()
    firebase_auth.set_custom_user_claims(uid, {"admin": True})
    print(f"admin claim set for {uid}")


if __name__ == "__main__":
    uid = sys.argv[1] if len(sys.argv) > 1 else ""
    if not uid:
        print("usage: python scripts/make_admin.py <uid>")
        sys.exit(1)
    asyncio.run(main(uid))
