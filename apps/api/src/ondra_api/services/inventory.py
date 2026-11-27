"""Importing a dealer's inventory file into `vehicles` (BUILD_PLAN.md §8). The reading and the decisions are plain
functions in `ondra_core.inventory_feed`; this applies them inside the dealer's tenant session and records the
outcome on the dealer's `inventory_feed` integration, which is what Settings shows as its health."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from ondra_core import inventory_feed as feed
from ondra_core.models import AuditLog, Event, Integration, Vehicle
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def _label(c: feed.Car) -> str:
    price = f", ${c.price:,.0f}" if c.price is not None else ""
    return f"{c.year} {c.make} {c.model}{price} ({c.stock})"


async def feed_integration(db: AsyncSession) -> Integration:
    row = (await db.execute(select(Integration).where(Integration.kind == "inventory_feed").limit(1))).scalar_one_or_none()
    if row is None:
        row = Integration(kind="inventory_feed", config={}, status="disconnected")
        db.add(row)
        await db.flush()
    return row


async def import_inventory(db: AsyncSession, text: str, filename: str = "", *, source: str = "upload", whole_lot: bool = False,
                           dry_run: bool = False, user_id: uuid.UUID | None = None) -> dict:
    """Read a file and apply it (or, with `dry_run`, only say what would happen). `whole_lot`: this file is every
    car the dealer has, so feed cars it doesn't list are marked sold. Hand-entered cars are never marked sold."""
    parsed = feed.parse(text, filename)
    now = datetime.now(UTC)
    if parsed.error:
        out = {"ok": False, "error": parsed.error}
        if not dry_run:
            integ = await feed_integration(db)
            integ.status = "error"
            integ.config = {**(integ.config or {}), "last": {**out, "at": now.isoformat(), "source": source, "file": filename[:120]}}
        return out
    rows = (await db.execute(select(Vehicle))).scalars().all()
    by_id = {str(v.id): v for v in rows}
    existing = [feed.Existing(str(v.id), v.stock_number, v.vin, v.status, v.source_feed is not None,
                              feed.fingerprint(v.year, v.make, v.model, v.trim, v.price, v.mileage, v.status), tuple(v.photos or ()),
                              tuple((k, (v.raw or {})[k]) for k in ("color", "body", "seats") if k in (v.raw or {})))
                for v in rows]
    p = feed.plan(existing, parsed.cars, whole_lot=whole_lot)
    out = {
        "ok": True, "created": len(p.create), "updated": len(p.update), "unchanged": p.unchanged, "sold": len(p.mark_sold),
        "skipped": parsed.skipped[:50], "skipped_count": len(parsed.skipped), "duplicates": parsed.duplicates, "partial": p.partial,
        "columns": parsed.columns, "unknown_columns": parsed.unknown_columns[:30],
        "examples": {"created": [_label(c) for c in p.create[:5]], "updated": [_label(c) for _, c in p.update[:5]],
                     "sold": [f"{by_id[i].year} {by_id[i].make} {by_id[i].model} ({by_id[i].stock_number})" for i in p.mark_sold[:5]]},
    }
    if dry_run:
        return out

    def apply(v: Vehicle, c: feed.Car) -> None:
        v.stock_number, v.vin, v.year, v.make, v.model, v.trim = c.stock, c.vin, c.year, c.make, c.model, c.trim
        v.price, v.mileage = c.price, c.mileage
        if c.status:
            v.status = c.status
        if c.photos:
            v.photos = list(c.photos)
        v.raw = {**(v.raw or {}), **dict(c.extra)}  # a hand-entered car stays hand-entered even when a file updates it

    for c in p.create:
        v = Vehicle(stock_number=c.stock, vin=c.vin, year=c.year, make=c.make, model=c.model, status=c.status or "available",
                    source_feed=source, raw={})
        apply(v, c)
        v.source_feed = source
        db.add(v)
    for vid, c in p.update:
        apply(by_id[vid], c)
    for vid in p.mark_sold:
        by_id[vid].status = "sold"
    integ = await feed_integration(db)
    integ.status = "warning" if (p.partial or parsed.skipped) else "ok"
    integ.last_sync_at = now
    summary = {k: out[k] for k in ("ok", "created", "updated", "unchanged", "sold", "skipped_count", "partial")}
    integ.config = {**(integ.config or {}), "last": {**summary, "at": now.isoformat(), "source": source, "file": filename[:120]}}
    db.add(Event(type="inventory.imported", payload={**summary, "source": source}))
    db.add(AuditLog(actor_type="user" if user_id else "system", actor_user_id=user_id, action="inventory.import",
                    resource="vehicles", before=None, after={**summary, "source": source, "file": filename[:120]}))
    await db.flush()
    return out
