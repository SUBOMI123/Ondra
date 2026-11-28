"""Integrations (BUILD_PLAN.md §8, Step 7): inventory import, the CRM lead push and the DMS, with their health."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from ondra_core import adf
from ondra_core.inventory_feed import MAX_BYTES
from ondra_core.models import AuditLog, ChannelAddress, Tenant
from ondra_core.permissions import Perm, has_perm
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.deps import Caller, get_db, require
from ondra_api.services import crm, feed_fetch
from ondra_api.services import dms as dms_service
from ondra_api.services.inventory import feed_integration, import_inventory
from ondra_api.services.jobs import enqueue

router = APIRouter(tags=["integrations"])


class ImportIn(BaseModel):
    filename: str = Field("", max_length=200)
    content: str = Field(max_length=MAX_BYTES + 1024)  # the file's text; CSV or XML
    # This file is every car on the lot: feed cars it doesn't list are marked sold. Off: only add and update.
    whole_lot: bool = False
    dry_run: bool = True  # say what would change without changing it


def _may_import(caller: Caller) -> None:
    if not (has_perm(caller.role, Perm.VEHICLES_WRITE) or has_perm(caller.role, Perm.INTEGRATIONS_MANAGE)):
        raise HTTPException(403, "Only admins and managers can import inventory.")


@router.post("/inventory/import")
async def import_file(body: ImportIn, ctx: tuple[Caller, AsyncSession] = Depends(get_db)) -> dict:
    """Preview (`dry_run`) or apply an inventory file. A file that can't be read at all is a 422 with the reason."""
    caller, db = ctx
    _may_import(caller)
    out = await import_inventory(db, body.content, body.filename, source="upload", whole_lot=body.whole_lot,
                                 dry_run=body.dry_run, user_id=caller.user_id)
    if not out["ok"]:
        if not body.dry_run:
            await db.commit()  # keep the failed attempt on the integration's health before answering
        raise HTTPException(422, out["error"])
    return out


# --- settings and health -------------------------------------------------------------------------------------------

class CrmIn(BaseModel):
    email: str = Field("", max_length=200)  # the CRM's lead-intake address
    active: bool = True


class FeedIn(BaseModel):
    url: str = Field("", max_length=1000)
    every_hours: Literal[0, 1, 6, 24] = 0  # 0: no scheduled fetch


class DmsIn(BaseModel):
    provider: Literal["off", "mock", "csv"]


class UploadIn(BaseModel):
    filename: str = Field("", max_length=200)
    content: str = Field(max_length=MAX_BYTES + 1024)


def _audit(db: AsyncSession, caller: Caller, request: Request, action: str, before, after) -> None:
    db.add(AuditLog(actor_type="user", actor_user_id=caller.user_id, action=action, resource="integrations",
                    before=before, after=after, ip=request.client.host if request.client else None))


def _health(integ, set_up: bool) -> dict:
    """One shape for every integration: off, ok, warning or error, when it last worked, and the last outcome."""
    last = dict((integ.config or {}).get("last") or {}) if integ else {}
    state = "off" if not set_up else (integ.status if integ.status in ("ok", "warning", "error") else "ok")
    return {"state": state, "last_ok_at": integ.last_sync_at.isoformat() if integ and integ.last_sync_at else None, "last": last}


@router.get("/integrations")
async def get_integrations(ctx: tuple[Caller, AsyncSession] = Depends(get_db)) -> dict:
    caller, db = ctx
    c, f, d = await crm.crm_integration(db), await feed_integration(db, create=False), await dms_service.dms_integration(db)
    ccfg, fcfg, dcfg = (c.config or {}) if c else {}, (f.config or {}) if f else {}, (d.config or {}) if d else {}  # reading creates nothing
    has_email = (await db.execute(select(ChannelAddress.id).where(ChannelAddress.channel == "email", ChannelAddress.active.is_(True)).limit(1))).first()
    return {
        "crm": {"email": ccfg.get("email", ""), "active": bool(ccfg.get("active")), "has_sender": bool(has_email),
                **_health(c, bool(ccfg.get("active") and ccfg.get("email")))},
        "inventory": {"url": fcfg.get("url", ""), "every_hours": int(fcfg.get("every_hours") or 0),
                      **_health(f, bool(fcfg.get("last") or fcfg.get("url")))},
        "dms": {"provider": dcfg.get("provider", "off"), "orders": len(dcfg.get("orders", [])) if dcfg.get("provider") == "csv" else None,
                **_health(d, dcfg.get("provider", "off") != "off")},
        "can_edit": has_perm(caller.role, Perm.INTEGRATIONS_MANAGE),
        "can_import": has_perm(caller.role, Perm.VEHICLES_WRITE) or has_perm(caller.role, Perm.INTEGRATIONS_MANAGE),
    }


@router.put("/integrations/crm")
async def put_crm(body: CrmIn, request: Request, ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.INTEGRATIONS_MANAGE))) -> dict:
    caller, db = ctx
    email = body.email.strip().lower()
    if body.active and not crm.valid_email(email):
        raise HTTPException(422, "Enter the email address your CRM gives you for incoming leads.")
    integ = await crm.crm_integration(db, create=True)
    before = {k: (integ.config or {}).get(k) for k in ("email", "active")}
    integ.config = {**(integ.config or {}), "email": email, "active": body.active}
    integ.status = "ok" if body.active else "disconnected"
    _audit(db, caller, request, "integrations.crm", before, {"email": email, "active": body.active})
    return {"email": email, "active": body.active}


@router.post("/integrations/crm/test")
async def test_crm(ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.INTEGRATIONS_MANAGE))) -> dict:
    """Send a clearly marked test lead to the CRM address, so the dealer can see it arrive."""
    _caller, db = ctx
    tenant = (await db.execute(select(Tenant).limit(1))).scalar_one()
    lead = adf.Lead(id=f"test-{uuid.uuid4().hex[:8]}", requested_at=datetime.now(UTC), vendor=tenant.name, first_name="Test", last_name="Lead",
                    email="test.lead@example.com", phone="+12145550199", comments="TEST LEAD from Ondra. Safe to delete. Sent to check that your CRM receives leads.",
                    vehicle=adf.Vehicle(year=datetime.now(UTC).year, make="Test", model="Vehicle", comments="Not a real enquiry."))
    ok, why = await crm.send_adf(db, adf.build(lead), "TEST lead from Ondra (safe to delete)")
    integ = await crm.crm_integration(db, create=True)
    crm._record(integ, ok, "Test lead sent." if ok else why)
    if not ok:
        await db.commit()
        raise HTTPException(502, f"Couldn't send the test lead: {why}")
    return {"sent": True}


@router.put("/integrations/inventory-feed")
async def put_feed(body: FeedIn, request: Request, ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.INTEGRATIONS_MANAGE))) -> dict:
    caller, db = ctx
    url = body.url.strip()
    if url or body.every_hours:
        try:
            url = feed_fetch.check_url(url)
        except feed_fetch.FeedError as e:
            raise HTTPException(422, str(e)) from None
    integ = await feed_integration(db)
    before = {k: (integ.config or {}).get(k) for k in ("url", "every_hours")}
    schedule_id = uuid.uuid4().hex  # jobs lined up for an older schedule see they're stale and stop
    integ.config = {**(integ.config or {}), "url": url, "every_hours": body.every_hours, "schedule_id": schedule_id}
    if url and body.every_hours:
        enqueue(db, "inventory_fetch", {"for": schedule_id})  # fetch now, then on the schedule
    _audit(db, caller, request, "integrations.inventory_feed", before, {"url": url, "every_hours": body.every_hours})
    return {"url": url, "every_hours": body.every_hours}


@router.put("/integrations/dms")
async def put_dms(body: DmsIn, request: Request, ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.INTEGRATIONS_MANAGE))) -> dict:
    caller, db = ctx
    integ = await dms_service.dms_integration(db, create=True)
    before = (integ.config or {}).get("provider", "off")
    if body.provider == "csv" and not (integ.config or {}).get("orders"):
        raise HTTPException(422, "Upload a repair-order export first.")
    integ.config = {**(integ.config or {}), "provider": body.provider}
    integ.status = "disconnected" if body.provider == "off" else "ok"
    _audit(db, caller, request, "integrations.dms", {"provider": before}, {"provider": body.provider})
    return {"provider": body.provider}


@router.post("/integrations/dms/upload")
async def upload_dms(body: UploadIn, request: Request, ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.INTEGRATIONS_MANAGE))) -> dict:
    caller, db = ctx
    out = await dms_service.upload_repair_orders(db, body.content, body.filename)
    if not out["ok"]:
        await db.commit()
        raise HTTPException(422, out["error"])
    _audit(db, caller, request, "integrations.dms.upload", None, {"loaded": out["loaded"], "skipped": out["skipped_count"], "file": body.filename[:120]})
    return out
