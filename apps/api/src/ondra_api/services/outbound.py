"""Sending a stored outbound message. Every send goes through here: Ondra's replies, approved drafts and staff
replies alike, so the last product-rule gate (opt-outs on every channel, no AI to VIPs) can't be skipped.

The message row is written first (status queued) by the caller. `deliver` re-checks the gate, sends outside any
transaction, then records the outcome.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from ondra_core.agent.policy import may_send_outbound
from ondra_core.channels.base import OutboundMessage
from ondra_core.models import ChannelAddress, Contact, ContactIdentity, Conversation, Event, Message
from sqlalchemy import select

from ondra_api.channels import adapter_for
from ondra_api.db import tenant_session


class Blocked(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class Delivery:
    ok: bool
    error: str | None = None


async def deliver(tenant_id: uuid.UUID, message_id: uuid.UUID) -> Delivery:
    from ondra_api.services.inbound import contact_opted_out

    async with tenant_session(tenant_id) as db:
        m = await db.get(Message, message_id)
        conv = await db.get(Conversation, m.conversation_id)
        contact = await db.get(Contact, conv.contact_id)
        ok, why = may_send_outbound(contact_is_vip=contact.is_vip, contact_opted_out=await contact_opted_out(db, contact.id),
                                    author_type=m.author_type)
        if not ok:
            m.status = "failed"
            db.add(Event(type="message.blocked", payload={"message_id": str(m.id), "reason": why}))
            raise Blocked(why)
        kinds = ("email",) if conv.channel == "email" else ("phone", "whatsapp")
        to_address = (await db.execute(
            select(ContactIdentity.value).where(ContactIdentity.contact_id == contact.id, ContactIdentity.kind.in_(kinds))
            .order_by(ContactIdentity.verified.desc()).limit(1)
        )).scalar_one_or_none()
        sender = (await db.execute(
            select(ChannelAddress).where(ChannelAddress.channel == conv.channel, ChannelAddress.active.is_(True)).limit(1)
        )).scalar_one_or_none()
        if to_address is None or sender is None:
            m.status = "failed"
            reason = "no customer address" if to_address is None else f"no active {conv.channel} channel"
            db.add(Event(type="message.send_failed", payload={"message_id": str(m.id), "error": reason}))
            return Delivery(False, reason)
        out = OutboundMessage(channel=conv.channel, to_address=to_address, from_address=sender.address, body=m.body or "")
        provider = sender.provider

    adapter = adapter_for(out.channel, provider)
    res = await adapter.send(out)
    async with tenant_session(tenant_id) as db:
        m = await db.get(Message, message_id)
        m.status = "sent" if res.ok else "failed"
        m.provider = adapter.provider
        m.provider_message_id = res.provider_message_id
        if res.ok:
            conv = await db.get(Conversation, m.conversation_id)
            conv.status = "waiting_customer"
            from ondra_api.services.follow_ups import on_sent

            await on_sent(db, m, conv, await db.get(Contact, conv.contact_id))  # start or advance their follow-ups
        else:
            db.add(Event(type="message.send_failed", payload={"message_id": str(message_id), "error": res.error}))
    return Delivery(res.ok, res.error)
