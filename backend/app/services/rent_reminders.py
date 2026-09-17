from datetime import date

from app.core import db
from app.services.fcm import notify


async def find_due_leases(today: date) -> list[dict]:
    if today.day < 5:
        return []
    due_month = f"{today.year:04d}-{today.month:02d}"
    leases = await db.list_collection_group("land_leases")
    rows = []
    for entry in leases:
        lease = entry["doc"]
        if lease.get("status") != "active":
            continue
        landlord_uid = entry["path"].split("/")[1]
        payments = await db.list_subdocs(f"{entry['path']}/land_leases/{lease['id']}/payments")
        if any(p.get("month") == due_month for p in payments):
            continue
        rows.append({"lease": lease, "landlordUid": landlord_uid, "dueMonth": due_month})
    return rows


async def run_rent_reminders(today: date | None = None) -> dict:
    today = today or date.today()
    due = await find_due_leases(today)
    reminded = 0
    for row in due:
        lease = row["lease"]
        landlord_uid = row["landlordUid"]
        if await _already_reminded(landlord_uid, lease["id"], row["dueMonth"]):
            continue
        # Tenant is not necessarily an app user (phone only) — tenant SMS is a Day 13 X4 follow-up.
        await notify(
            landlord_uid,
            "किराया लंबित",
            f"{lease['tenantName']} का {row['dueMonth']} का किराया ₹{lease['monthlyRentRupees']} लंबित है",
            {"type": "rent_reminder", "leaseId": lease["id"], "month": row["dueMonth"]},
        )
        reminded += 1
    return {"reminded": reminded}


async def _already_reminded(landlord_uid: str, lease_id: str, month: str) -> bool:
    notifications = await db.list_subdocs(f"users/{landlord_uid}/notifications")
    return any(
        n.get("data", {}).get("type") == "rent_reminder"
        and n.get("data", {}).get("leaseId") == lease_id
        and n.get("data", {}).get("month") == month
        for n in notifications
    )
