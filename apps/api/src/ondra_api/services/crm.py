"""Pushing qualified leads to the dealer's CRM as an ADF/XML email (BUILD_PLAN.md §8, Step 7).

    maybe_queue()   called when the AI records lead details or hands off: if the dealer has a CRM address and this
                    lead is now worth a salesperson's time, queue the push (a minute later, so details captured in
                    the same conversation go out together).
    push()          the job: build the ADF from the lead as it stands now, email it once, record the outcome on the
                    `crm_adf` integration (its health in Settings).

A lead qualifies when it's a sales lead, we know what they want, and there's a phone number or email to reach them
on. VIPs are never pushed: they're the owner's own contacts, not CRM leads.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from ondra_core import adf
from ondra_core.channels.base import OutboundMessage
from ondra_core.models import (
    ChannelAddress,
    Contact,
    ContactIdentity,
    Deal,
    Event,
    Integration,
    Job,
    Task,
    Tenant,
    Vehicle,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.channels import adapter_for
from ondra_api.db import tenant_session
from ondra_api.services.jobs import enqueue

log = logging.getLogger("ondra.crm")
PUSH_DELAY = timedelta(seconds=60)
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def valid_email(value: str) -> bool:
    return bool(_EMAIL.match(value or "")) and len(value) <= 200


async def crm_integration(db: AsyncSession, create: bool = False) -> Integration | None:
    row = (await db.execute(select(Integration).where(Integration.kind == "crm_adf").limit(1))).scalar_one_or_none()
    if row is None and create:
        row = Integration(kind="crm_adf", config={}, status="disconnected")
        db.add(row)
        await db.flush()
    return row


def _on(integ: Integration | None) -> bool:
    return bool(integ and (integ.config or {}).get("active") and valid_email((integ.config or {}).get("email", "")))


def qualified(deal: Deal, contact: Contact, identities: list[ContactIdentity]) -> bool:
    wants = deal.vehicle_of_interest or {}
    reachable = any(i.kind in ("phone", "whatsapp", "email") for i in identities)
    return deal.type == "sales" and not contact.is_vip and reachable and bool(wants.get("description") or wants.get("stock"))


async def maybe_queue(db: AsyncSession, contact: Contact) -> bool:
    """Queue this customer's open sales lead for the CRM if it qualifies and hasn't been sent. True if queued."""
    if not _on(await crm_integration(db)):
        return False
    deal = (await db.execute(select(Deal).where(Deal.contact_id == contact.id, Deal.type == "sales", Deal.crm_pushed_at.is_(None),
                                                Deal.stage.notin_(("won", "lost"))).order_by(Deal.created_at.desc()).limit(1))).scalar_one_or_none()
    if deal is None:
        return False
    identities = list((await db.execute(select(ContactIdentity).where(ContactIdentity.contact_id == contact.id))).scalars())
    if not qualified(deal, contact, identities):
        return False
    waiting = (await db.execute(select(Job.id).where(Job.kind == "crm_push", Job.status.in_(("queued", "running")),
                                                     Job.payload["deal_id"].astext == str(deal.id)).limit(1))).first()
    if waiting:
        return False  # already on its way
    enqueue(db, "crm_push", {"deal_id": str(deal.id)}, run_at=datetime.now(UTC) + PUSH_DELAY)
    return True


async def _vehicle(db: AsyncSession, wants: dict) -> adf.Vehicle:
    """The car they asked about, as far as we can tell. A stock number names it exactly. Otherwise, if what they
    described names one make and model we stock, those are filled in; never a guess at a particular car."""
    described = str(wants.get("description") or "")
    v = None
    if wants.get("stock"):
        v = (await db.execute(select(Vehicle).where(Vehicle.stock_number.ilike(str(wants["stock"]))).limit(1))).scalar_one_or_none()
    if v is not None:
        return adf.Vehicle(year=v.year, make=v.make, model=v.model, vin=v.vin, stock=v.stock_number, trim=v.trim, odometer=v.mileage,
                           price=float(v.price) if v.price is not None else None, comments=described or None)
    pairs = (await db.execute(select(Vehicle.make, Vehicle.model).distinct())).all()
    text_ = described.lower()
    hits = {(mk, md) for mk, md in pairs if md and re.search(rf"(?<![a-z0-9]){re.escape(md.lower())}(?![a-z0-9])", text_)}
    if len(hits) == 1:
        make, model = next(iter(hits))
        year = re.search(r"\b(19[5-9]\d|20[0-4]\d)\b", described)
        return adf.Vehicle(year=int(year.group(1)) if year else None, make=make, model=model, comments=described)
    return adf.Vehicle(comments=described or None)


async def build_lead(db: AsyncSession, deal: Deal, *, resend: bool = False) -> adf.Lead:
    contact = await db.get(Contact, deal.contact_id)
    tenant = (await db.execute(select(Tenant).limit(1))).scalar_one()
    ids = list((await db.execute(select(ContactIdentity).where(ContactIdentity.contact_id == contact.id)
                                 .order_by(ContactIdentity.verified.desc(), ContactIdentity.created_at))).scalars())
    phone = next((i.value for i in ids if i.kind in ("phone", "whatsapp")), None)
    email = next((i.value for i in ids if i.kind == "email"), None)
    name = (contact.display_name or "").strip()
    known = bool(name) and not name.startswith("+") and "@" not in name
    parts = name.split()
    wants = dict(deal.vehicle_of_interest or {})
    notes = []
    for label, value in (("Budget", f"up to ${float(deal.budget_max):,.0f}" if deal.budget_max else None), ("Paying by", deal.payment_method),
                         ("Timeline", deal.timeline), ("Deliver to", deal.destination)):
        if value:
            notes.append(f"{label}: {value}.")
    for k, v in wants.items():
        if k not in ("description", "stock") and v not in (None, ""):
            notes.append(f"{k.replace('_', ' ').capitalize()}: {v}.")
    brief = (await db.execute(select(Task.brief).where(Task.contact_id == contact.id, Task.source == "ai_handoff", Task.brief.isnot(None))
                              .order_by(Task.created_at.desc()).limit(1))).scalar_one_or_none()
    if brief:
        notes.append(brief.strip())
    notes.append(f"Came in by {deal.source_channel or 'message'}, captured by Ondra.")
    sender = (await db.execute(select(ChannelAddress.address).where(ChannelAddress.channel == "email", ChannelAddress.active.is_(True))
                               .limit(1))).scalar_one_or_none()
    method = (deal.payment_method or "").lower()
    return adf.Lead(
        id=str(deal.id), requested_at=deal.created_at.astimezone(ZoneInfo((tenant.timezones or ["America/Chicago"])[0])),
        vendor=tenant.name, first_name=parts[0] if known else None, last_name=" ".join(parts[1:]) or None if known else None,
        full_name=None if known else (phone or email or "Unknown"), email=email, phone=phone, vehicle=await _vehicle(db, wants),
        comments=" ".join(notes)[:2000], timeframe=deal.timeline, budget_max=float(deal.budget_max) if deal.budget_max else None,
        finance_method="cash" if "cash" in method else "lease" if "lease" in method else "finance" if "financ" in method else None,
        vendor_email=sender, resend=resend)


async def send_adf(db: AsyncSession, xml: str, subject: str) -> tuple[bool, str]:
    """Email an ADF document to the dealer's CRM address. Plain text, the XML and nothing else (see ondra_core.adf)."""
    integ = await crm_integration(db)
    to = (integ.config or {}).get("email", "") if integ else ""
    if not valid_email(to):
        return False, "No CRM lead address is set."
    sender = (await db.execute(select(ChannelAddress).where(ChannelAddress.channel == "email", ChannelAddress.active.is_(True))
                               .limit(1))).scalar_one_or_none()
    if sender is None:
        return False, "Add an email address under Channels first: leads are emailed from it."
    res = await adapter_for("email", sender.provider).send(
        OutboundMessage(channel="email", to_address=to, from_address=sender.address, body=xml, subject=subject))
    return (True, "") if res.ok else (False, res.error or "The email provider refused it.")


def _record(integ: Integration, ok: bool, detail: str) -> None:
    now = datetime.now(UTC)
    integ.status = "ok" if ok else "error"
    if ok:
        integ.last_sync_at = now
    integ.config = {**(integ.config or {}), "last": {"ok": ok, "at": now.isoformat(), "detail": detail[:300]}}


async def push(tenant_id: uuid.UUID, payload: dict) -> str:
    """The job. Returns what happened."""
    async with tenant_session(tenant_id) as db:
        deal = await db.get(Deal, uuid.UUID(payload["deal_id"]))
        integ = await crm_integration(db)
        if deal is None:
            return "skipped: no deal"
        if deal.crm_pushed_at is not None:
            return "skipped: already sent"
        if not _on(integ):
            return "skipped: CRM push is off"
        contact = await db.get(Contact, deal.contact_id)
        if contact.is_vip:
            return "skipped: VIP"
        lead = await build_lead(db, deal)
        xml = adf.build(lead)
        wrong = adf.problems(xml)
        if wrong:  # never send a CRM something it will silently drop
            _record(integ, False, f"The lead couldn't be written as valid ADF: {wrong[0]}")
            log.error("invalid ADF for deal %s: %s", deal.id, wrong)
            return f"failed: invalid ADF ({wrong[0]})"
        who = " ".join(x for x in (lead.first_name, lead.last_name) if x) or "new customer"
        ok, why = await send_adf(db, xml, f"New lead from {lead.provider}: {who}")
        _record(integ, ok, "Lead sent." if ok else why)
        if ok:
            deal.crm_pushed_at = datetime.now(UTC)
            db.add(Event(type="lead.pushed_to_crm", payload={"deal_id": str(deal.id), "contact_id": str(contact.id)}))
            return "sent"
    # The failure is saved on the integration (above, committed) before the job is failed, so Settings shows it;
    # raising makes the job queue retry with backoff.
    raise RuntimeError(f"ADF push failed: {why}")
