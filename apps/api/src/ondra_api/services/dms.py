"""The dealer's DMS, chosen from their `dms` integration (BUILD_PLAN.md §8). `mock` is demo data; `csv` is a
repair-order export the dealer uploaded (kept on the integration); anything else means not connected."""

from __future__ import annotations

from datetime import UTC, datetime

from ondra_core import dms
from ondra_core.models import Integration
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def dms_integration(db: AsyncSession, create: bool = False) -> Integration | None:
    row = (await db.execute(select(Integration).where(Integration.kind == "dms").limit(1))).scalar_one_or_none()
    if row is None and create:
        row = Integration(kind="dms", config={"provider": "off"}, status="disconnected")
        db.add(row)
        await db.flush()
    return row


def adapter_from(integ: Integration | None) -> dms.DmsAdapter | None:
    cfg = (integ.config or {}) if integ else {}
    if cfg.get("provider") == "mock":
        return dms.MockDms()
    if cfg.get("provider") == "csv":
        return dms.CsvDms([dms.RepairOrder(**o) for o in cfg.get("orders", [])])
    return None


async def repair_order_status(db: AsyncSession, *, phones: list[str], emails: list[str], ro_number: str | None = None) -> dict:
    """What the AI is told. Only this customer's own repair orders, matched by their phone or email."""
    adapter = adapter_from(await dms_integration(db))
    if adapter is None:
        return {"found": False, "note": "The service system isn't connected, so repair status can't be looked up here. Hand off to service."}
    try:
        orders = await adapter.get_repair_orders(phones=phones, emails=emails)
    except Exception as exc:  # noqa: BLE001  a DMS outage becomes a handoff, never a guess
        return {"found": False, "note": f"The service system didn't answer ({type(exc).__name__}). Hand off to service."}
    live = [o for o in orders if o.status != "picked_up"] or orders[:1]
    if ro_number:
        wanted = [o for o in orders if o.number.lower().replace(" ", "") == ro_number.lower().replace(" ", "")]
        if not wanted:
            # Never confirm or deny someone else's repair order.
            return {"found": False, "note": "No repair order with that number under this customer's phone number or email. "
                                            "Hand off to service; don't ask them to prove who they are."}
        live = wanted
    if not live:
        return {"found": False, "note": "No repair order under this customer's phone number or email. Hand off to service."}
    return {"found": True, "repair_orders": [o.for_customer() for o in live[:3]],
            "note": "No completion time is available here; don't give or guess one."}


async def upload_repair_orders(db: AsyncSession, text: str, filename: str = "") -> dict:
    """Replace the CSV DMS's repair orders with this export."""
    orders, skipped, error = dms.parse_repair_orders(text)
    integ = await dms_integration(db, create=True)
    now = datetime.now(UTC)
    if error:
        integ.config = {**(integ.config or {}), "last": {"ok": False, "at": now.isoformat(), "detail": error}}
        if (integ.config or {}).get("provider") == "csv":
            integ.status = "error"
        return {"ok": False, "error": error}
    integ.config = {"provider": "csv", "orders": [o.__dict__ for o in orders], "file": filename[:120],
                    "last": {"ok": True, "at": now.isoformat(), "detail": f"{len(orders)} repair orders loaded.", "skipped": len(skipped)}}
    integ.status = "warning" if skipped else "ok"
    integ.last_sync_at = now
    return {"ok": True, "loaded": len(orders), "skipped": skipped[:50], "skipped_count": len(skipped)}
