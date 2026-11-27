"""The owner's line to Ondra on WhatsApp (BUILD_PLAN.md §4.4).

Who counts as the owner: an active user with the owner role whose mobile (Settings > Team) is the number writing in,
and only on WhatsApp. WhatsApp verifies the sender's number; a text message's sender can be faked, so the assistant
never answers over SMS. The owner writes to any of the dealership's own WhatsApp numbers.

Sending to the owner follows WhatsApp's rule: free text (and buttons) only within 24 hours of the owner's last
message to us; outside that, an approved template. Every message either way is kept in `assistant_messages`.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from ondra_core.channels.base import OutboundMessage
from ondra_core.models import AssistantMessage, ChannelAddress, Contact, Task, Tenant, User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.channels import adapter_for
from ondra_api.db import tenant_session

log = logging.getLogger("ondra.owner")
WINDOW = timedelta(hours=24)
# Templates Ondra needs approved in the dealer's WhatsApp Business account before anything can be sent to an owner
# who hasn't written in the last 24 hours. Names and variable order are what the adapter sends.
# TODO(verify): wording and category are approved per WhatsApp Business account by Meta; these are proposals.
TEMPLATES = {
    "ondra_morning_briefing": "Good morning {{1}}. {{2}} today: {{3}} VIPs waiting, {{4}} hot leads, {{5}} drafts to approve, "
                              "{{6}} overdue tasks, {{7}} appointments. Reply here to ask about any of them.",
    "ondra_alert": "{{1}}, this needs you: {{2}} Reply here and I'll help.",
}
DEFAULTS = {"briefing_on": False, "briefing_time": "07:30", "alerts_on": True}


def settings_of(tenant: Tenant) -> dict:
    return {**DEFAULTS, **((tenant.settings or {}).get("owner_assistant") or {})}


async def owner_by_phone(db: AsyncSession, phone: str) -> User | None:
    return (await db.execute(select(User).where(User.phone == phone, User.role == "owner", User.active.is_(True)).limit(1))).scalar_one_or_none()


async def owners(db: AsyncSession) -> list[User]:
    """Owners who can be reached: active, with a mobile on file."""
    return list((await db.execute(select(User).where(User.role == "owner", User.active.is_(True), User.phone.isnot(None))
                                  .order_by(User.created_at))).scalars())


async def in_window(db: AsyncSession, user_id: uuid.UUID, now: datetime | None = None) -> bool:
    last = (await db.execute(select(AssistantMessage.created_at).where(AssistantMessage.user_id == user_id, AssistantMessage.direction == "in")
                             .order_by(AssistantMessage.created_at.desc()).limit(1))).scalar_one_or_none()
    return last is not None and (now or datetime.now(UTC)) - last < WINDOW


async def send_to_owner(tenant_id: uuid.UUID, user_id: uuid.UUID, text: str, *, kind: str = "reply", buttons: list[dict] | None = None,
                        template: dict | None = None, meta: dict | None = None) -> bool:
    """Send one message to an owner and keep it. `template` is used when the owner is outside the 24-hour window
    (a message with neither a window nor a template can't be sent, and is recorded as failed with the reason)."""
    async with tenant_session(tenant_id) as db:
        user = await db.get(User, user_id)
        sender = (await db.execute(select(ChannelAddress).where(ChannelAddress.channel == "whatsapp", ChannelAddress.active.is_(True))
                                   .order_by(ChannelAddress.created_at).limit(1))).scalar_one_or_none()
        row = AssistantMessage(user_id=user_id, direction="out", kind=kind, body=text, meta=dict(meta or {}))
        db.add(row)
        await db.flush()
        row_id = row.id
        problem = None
        if user is None or not user.phone:
            problem = "no mobile on file for the owner"
        elif sender is None:
            problem = "the dealership has no WhatsApp number connected"
        inside = await in_window(db, user_id)
        if problem is None and not inside and template is None:
            problem = "outside WhatsApp's 24-hour window and no template fits"
        if problem:
            row.status, row.meta = "failed", {**row.meta, "error": problem}
            log.warning("not sent to owner: %s", problem)
            return False
        out = OutboundMessage(channel="whatsapp", to_address=user.phone, from_address=sender.address, body=text,
                              buttons=buttons if inside else None, template=None if inside else template)
        provider = sender.provider
    res = await adapter_for("whatsapp", provider).send(out)
    async with tenant_session(tenant_id) as db:
        row = await db.get(AssistantMessage, row_id)
        row.provider_message_id = res.provider_message_id
        if not res.ok:
            row.status, row.meta = "failed", {**row.meta, "error": res.error}
        elif out.template:
            row.meta = {**row.meta, "template": out.template["name"]}
    return res.ok


async def deliver_alert(tenant_id: uuid.UUID, payload: dict) -> str:
    """The job behind every alert raised for the owner (queued by a database trigger as the alert is recorded)."""
    async with tenant_session(tenant_id) as db:
        tenant = (await db.execute(select(Tenant).limit(1))).scalar_one()
        if not settings_of(tenant)["alerts_on"]:
            return "skipped: alerts are off"
        task = await db.get(Task, uuid.UUID(payload["task_id"])) if payload.get("task_id") else None
        contact_id = payload.get("contact_id") or (str(task.contact_id) if task and task.contact_id else None)
        contact = await db.get(Contact, uuid.UUID(contact_id)) if contact_id else None
        # The VIP's own owner if they have one, else every owner.
        handler = await db.get(User, contact.vip_owner_user_id) if contact is not None and contact.vip_owner_user_id else None
        to = [handler] if handler is not None and handler.active and handler.phone else await owners(db)
        reason = str(payload.get("reason") or "Something needs you").rstrip(".")
        who = contact.display_name if contact is not None else None
        line = f"{who}: {reason}." if who and who.lower() not in reason.lower() else f"{reason}."
        if payload.get("repeat"):
            line = f"Still waiting ({payload['repeat']}). {line}"
        targets = [(u.id, u.name.split()[0]) for u in to]
    if not targets:
        return "skipped: no owner with a mobile on file"
    sent = 0
    for user_id, first in targets:
        sent += await send_to_owner(tenant_id, user_id, line, kind="alert", meta={"task_id": payload.get("task_id")},
                                    template={"name": "ondra_alert", "language": "en_US", "params": [first, line]})
    return f"sent to {sent} of {len(targets)}"
