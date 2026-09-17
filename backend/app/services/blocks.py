from app.core import db


def _blocks_path(uid: str) -> str:
    return f"users/{uid}/blocks"


async def blocked_pair(a: str, b: str) -> bool:
    return bool(
        await db.get_subdoc_at(_blocks_path(a), b)
        or await db.get_subdoc_at(_blocks_path(b), a)
    )


async def list_blocked_ids(uid: str) -> set[str]:
    docs = await db.list_subdocs(_blocks_path(uid))
    return {d["id"] for d in docs}
