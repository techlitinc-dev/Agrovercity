from datetime import date, datetime, timedelta, timezone

from app.core import db


async def _commission_config() -> dict:
    config = await db.get_doc("platform_config", "settlements")
    if config is None:
        config = {"transportPct": 10, "equipmentRentalPct": 12, "brokerPct": 2}
        await db.set_doc("platform_config", "settlements", config)
    return config


async def _vehicle_owner_uid(vehicle_id: str | None) -> str | None:
    if not vehicle_id:
        return None
    vehicle = await db.get_doc("vehicles", vehicle_id)
    return vehicle.get("ownerId") if vehicle else None


async def _equipment_owner_uid(equipment_id: str | None) -> str | None:
    if not equipment_id:
        return None
    equipment = await db.get_doc("equipment", equipment_id)
    return equipment.get("ownerId") if equipment else None


def _in_period(day: str | None, start: str, end: str) -> bool:
    return bool(day) and start <= day <= end


async def run_settlements(period_start: str, period_end: str) -> dict:
    config = await _commission_config()
    earnings: dict[tuple[str, str], int] = {}
    sources: dict[tuple[str, str], list[str]] = {}

    bookings = await db.query("transport_bookings", [], limit=10000)
    for b in bookings:
        if b.get("status") != "delivered" or not _in_period(b.get("date"), period_start, period_end):
            continue
        uid = await _vehicle_owner_uid(b.get("vehicleId"))
        if not uid:
            continue
        key = ("transport", uid)
        earnings[key] = earnings.get(key, 0) + int(b.get("fare", 0))
        sources.setdefault(key, []).append(b["id"])

    eq_bookings = await db.query("equipment_bookings", [], limit=10000)
    for b in eq_bookings:
        if b.get("status") != "booked" or not _in_period(b.get("date"), period_start, period_end):
            continue
        uid = await _equipment_owner_uid(b.get("equipmentId"))
        if not uid:
            continue
        key = ("equipmentRental", uid)
        earnings[key] = earnings.get(key, 0) + int(b.get("priceRupees", 0))
        sources.setdefault(key, []).append(b["id"])

    deals = await db.query("broker_deals", [("status", "==", "completed")], limit=10000)
    for d in deals:
        if not _in_period(d.get("completedAt") or d.get("date"), period_start, period_end):
            continue
        uid = d.get("brokerId")
        if not uid:
            continue
        key = ("broker", uid)
        earnings[key] = earnings.get(key, 0) + int(d.get("value", 0))
        sources.setdefault(key, []).append(d["id"])

    created = updated = 0
    for (role, entity_id), gross in earnings.items():
        pct = config.get(f"{role}Pct", 0)
        commission = round(gross * pct / 100)
        net = gross - commission
        doc_id = f"st_{role}_{entity_id[:8]}_{period_start}"
        existing = await db.get_doc("settlements", doc_id)
        if existing is not None and existing.get("status") != "pending":
            continue
        doc = {
            "id": doc_id,
            "role": role,
            "entityId": entity_id,
            "periodStart": period_start,
            "periodEnd": period_end,
            "grossRupees": gross,
            "commissionRupees": commission,
            "netRupees": net,
            "status": "pending",
            "sourceIds": sources.get((role, entity_id), []),
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        await db.set_doc("settlements", doc_id, doc)
        if existing is None:
            created += 1
        else:
            updated += 1
    return {"created": created, "updated": updated}


def last_iso_week() -> tuple[str, str]:
    today = date.today()
    last_sunday = today - timedelta(days=today.weekday() + 1)
    last_monday = last_sunday - timedelta(days=6)
    return last_monday.isoformat(), last_sunday.isoformat()
