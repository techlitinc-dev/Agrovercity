from app.core import db
from firebase_admin import auth as firebase_auth

PURGE_SUBCOLLECTIONS = [
    "diary_entries",
    "crop_pnl",
    "vault_documents",
    "land_plots",
    "land_leases",
    "scheme_applications",
    "devices",
    "coin_ledger",
    "consents",
    "soil_tests",
]

FINANCIAL_COLLECTIONS = ["transport_bookings", "orders"]


async def purge_user(uid: str) -> dict:
    deleted = 0
    for sub in PURGE_SUBCOLLECTIONS:
        path = f"users/{uid}/{sub}"
        docs = await db.list_subdocs(path)
        for doc in docs:
            if sub == "land_leases":
                for payment in await db.list_subdocs(f"{path}/{doc['id']}/payments"):
                    await db.delete_subdoc_at(f"{path}/{doc['id']}/payments", payment["id"])
            await db.delete_subdoc_at(path, doc["id"])
            deleted += 1

    # Storage prefixes are skipped silently in dev mode (no Firebase).
    anonymized = 0
    anon_id = f"deleted:{uid[:8]}"
    for collection in FINANCIAL_COLLECTIONS:
        docs = await db.query(collection, [("userId", "==", uid)], limit=1000)
        for doc in docs:
            doc["userId"] = anon_id
            await db.set_doc(collection, doc["id"], doc)
            anonymized += 1

    await db.delete_doc("users", uid)
    firebase_auth.delete_user(uid)
    return {
        "subcollectionsDeleted": deleted,
        "authDeleted": True,
        "financialAnonymized": anonymized,
    }
