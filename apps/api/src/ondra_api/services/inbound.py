"""Inbound message handling (BUILD_PLAN.md §4.1): from a parsed webhook event to a stored message, a policy
decision, and (when allowed) an AI reply that is sent or saved as a draft.

    ingest()        one transaction: find the dealer, the contact and the conversation; store the message once
                    (idempotent on the provider's id); apply the pre-policy (consent, VIP, ai off); alert people.
    run_agent()     the AI turn, then the outbound gate, then send or draft. Runs after the webhook has answered.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from ondra_core.agent.llm import LLM, AnthropicLLM
from ondra_core.agent.orchestrator import Turn, run_turn
from ondra_core.agent.policy import Alert, InboundFacts, evaluate_inbound, may_send_outbound
from ondra_core.agent.prompt import CustomerFacts, DealerFacts
from ondra_core.channels.base import InboundMessage, OutboundMessage, StatusUpdate
from ondra_core.channels.identity import identity_kind
from ondra_core.models import (
    ChannelAddress,
    Consent,
    Contact,
    ContactIdentity,
    Conversation,
    Event,
    Message,
    Policy,
    Task,
    Tenant,
)
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.channels import adapter_for
from ondra_api.config import get_settings
from ondra_api.db import no_tenant_session, tenant_session
from ondra_api.services.agent_tools import DbToolBackend, assignee_for

log = logging.getLogger("ondra.inbound")

ALL_CHANNELS = ("sms", "whatsapp", "email", "phone")
HISTORY_LIMIT = 20


# --- the model, overridable in tests -----------------------------------------------------------------------------

def _default_llm() -> LLM | None:
    s = get_settings()
    if not s.anthropic_api_key:
        return None
    return AnthropicLLM(api_key=s.anthropic_api_key, model=s.model_conversation, effort=s.agent_effort,
                        base_url=s.anthropic_api_base)


llm_factory: Callable[[], LLM | None] = _default_llm


# --- helpers -----------------------------------------------------------------------------------------------------

def dealer_clock(tenant: Tenant, now: datetime | None = None) -> tuple[str, bool]:
    """('Tue 10:48 pm', open_now) in the dealer's first timezone."""
    tz = ZoneInfo((tenant.timezones or ["America/Chicago"])[0])
    local = (now or datetime.now(UTC)).astimezone(tz)
    label = local.strftime("%a %-I:%M %p").replace("AM", "am").replace("PM", "pm")
    hours = (tenant.business_hours or {}).get(local.strftime("%a").lower())
    open_now = bool(hours) and hours[0] <= local.strftime("%H:%M") < hours[1]
    return label, open_now


async def contact_opted_out(db: AsyncSession, contact_id: uuid.UUID) -> bool:
    """True if the latest consent record for any channel and purpose is an opt-out. One opt-out blocks all."""
    row = (await db.execute(text("""
        SELECT bool_or(status = 'opted_out') FROM (
          SELECT DISTINCT ON (channel, purpose) status FROM consents
          WHERE contact_id = :c ORDER BY channel, purpose, captured_at DESC, created_at DESC
        ) latest
    """), {"c": contact_id})).scalar()
    return bool(row)


async def _resolve_contact(db: AsyncSession, msg: InboundMessage) -> Contact:
    kinds = ("phone", "whatsapp") if msg.channel in ("sms", "whatsapp") else ("email",)
    ident = (await db.execute(
        select(ContactIdentity).where(ContactIdentity.kind.in_(kinds), ContactIdentity.value == msg.from_address)
        .order_by(ContactIdentity.verified.desc(), ContactIdentity.created_at).limit(1)
    )).scalar_one_or_none()
    if ident is None:
        contact = Contact(display_name=(msg.sender_name or msg.from_address)[:200], preferred_channel=msg.channel)
        db.add(contact)
        await db.flush()
        db.add(ContactIdentity(contact_id=contact.id, kind=identity_kind(msg.channel), value=msg.from_address))
        return contact
    contact = await db.get(Contact, ident.contact_id)
    for _ in range(5):  # follow merges
        if contact.merged_into_id is None:
            break
        contact = await db.get(Contact, contact.merged_into_id)
    if ident.kind != identity_kind(msg.channel):
        # Known by phone, now writing on WhatsApp from the same number: remember that too.
        await db.execute(insert(ContactIdentity).values(
            contact_id=contact.id, kind=identity_kind(msg.channel), value=msg.from_address
        ).on_conflict_do_nothing(constraint="contact_identities_unique"))
    return contact


async def _conversation(db: AsyncSession, contact: Contact, channel: str) -> Conversation:
    conv = (await db.execute(
        select(Conversation).where(Conversation.contact_id == contact.id, Conversation.channel == channel,
                                   Conversation.status != "closed").order_by(Conversation.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    if conv is None:
        # 'auto' here means "follow the dealer's policy"; draft mode is the dealer-wide switch in `policies`.
        conv = Conversation(contact_id=contact.id, channel=channel, ai_mode="auto")
        db.add(conv)
        await db.flush()
    return conv


async def _alert(db: AsyncSession, alert: Alert, contact: Contact, conv: Conversation) -> Task:
    preferred = contact.vip_owner_user_id if alert.to == "owner" else conv.assigned_user_id if alert.to == "assigned" else None
    role = "owner" if alert.to == "owner" else "sales" if alert.to == "assigned" else alert.to
    task = Task(title=f"{contact.display_name}: {alert.reason}", contact_id=contact.id, conversation_id=conv.id,
                assignee_user_id=await assignee_for(db, role, preferred), source="rule", urgency=alert.urgency,
                brief=alert.reason)
    db.add(task)
    await db.flush()
    # The owner's WhatsApp/push notification arrives with Step 8; the event is what the notifier will consume.
    db.add(Event(type="alert.created", payload={"task_id": str(task.id), "to": alert.to, "urgency": alert.urgency,
                                                "contact_id": str(contact.id), "reason": alert.reason}))
    return task


async def _record_consent(db: AsyncSession, contact: Contact, change: str, msg_id: uuid.UUID, channel: str) -> None:
    status = "opted_out" if change == "opted_out_all_channels" else "opted_in"
    # TODO(verify, counsel): START re-subscribes every channel the STOP covered. Confirm with counsel per channel.
    for ch in ALL_CHANNELS:
        for purpose in ("transactional", "marketing"):
            db.add(Consent(contact_id=contact.id, channel=ch, purpose=purpose, status=status, source=f"keyword:{channel}",
                           evidence={"message_id": str(msg_id)}))
    db.add(Event(type=f"consent.{status}", payload={"contact_id": str(contact.id), "via": channel}))


# --- ingest ------------------------------------------------------------------------------------------------------

@dataclass
class IngestResult:
    status: str  # stored | duplicate | unknown_address
    tenant_id: uuid.UUID | None = None
    message_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None
    run_ai: bool = False
    draft: bool = False
    reason: str = ""


async def find_tenant(channel: str, address: str) -> uuid.UUID | None:
    async with no_tenant_session() as db:
        return (await db.execute(text("SELECT channel_find_tenant(:c, :a)"), {"c": channel, "a": address})).scalar()


async def ingest(msg: InboundMessage) -> IngestResult:
    tenant_id = await find_tenant(msg.channel, msg.to_address)
    if tenant_id is None:
        log.warning("inbound to unknown %s address", msg.channel)
        return IngestResult("unknown_address")

    async with tenant_session(tenant_id) as db:
        contact = await _resolve_contact(db, msg)
        conv = await _conversation(db, contact, msg.channel)
        inserted = (await db.execute(
            insert(Message).values(
                conversation_id=conv.id, direction="inbound", author_type="customer", body=msg.body,
                attachments=msg.attachments, provider=msg.provider, provider_message_id=msg.provider_message_id,
                status="received",
            ).on_conflict_do_nothing(constraint="messages_provider_id").returning(Message.id)
        )).scalar_one_or_none()
        if inserted is None:
            # Providers retry (Meta for up to 36 hours). A message we've seen is never processed twice.
            return IngestResult("duplicate", tenant_id)
        conv.last_inbound_at = msg.received_at
        if conv.status == "waiting_customer":
            conv.status = "open"

        policy = (await db.execute(select(Policy).limit(1))).scalar_one_or_none()
        decision = evaluate_inbound(InboundFacts(
            channel=msg.channel,
            body=msg.body,
            contact_is_vip=contact.is_vip,
            contact_opted_out=await contact_opted_out(db, contact.id),
            conversation_ai_mode=conv.ai_mode,  # type: ignore[arg-type]
            tenant_draft_mode=policy.draft_mode if policy else True,
        ))
        if decision.consent_change:
            await _record_consent(db, contact, decision.consent_change, inserted, msg.channel)
        if decision.alert:
            await _alert(db, decision.alert, contact, conv)
        db.add(Event(type="message.received", payload={
            "message_id": str(inserted), "conversation_id": str(conv.id), "channel": msg.channel,
            "decision": decision.reason, "run_ai": decision.run_ai, "draft": decision.draft,
        }))
        return IngestResult("stored", tenant_id, inserted, conv.id, decision.run_ai, decision.draft, decision.reason)


async def mark_status(update: StatusUpdate) -> None:
    """Delivery receipts. TODO(step 3): find the tenant from the receiving address and update the message's status;
    for now they're logged only."""
    log.info("status %s for %s", update.status, update.provider_message_id)


# --- the AI turn -------------------------------------------------------------------------------------------------

@dataclass
class AgentOutcome:
    status: str  # sent | drafted | blocked | skipped | no_model | send_failed
    reply: str = ""
    message_id: uuid.UUID | None = None
    latency_ms: int = 0
    tools: list[str] | None = None


async def run_agent(tenant_id: uuid.UUID, conversation_id: uuid.UUID, message_id: uuid.UUID, draft: bool) -> AgentOutcome:
    started = time.monotonic()
    async with tenant_session(tenant_id) as db:
        conv = await db.get(Conversation, conversation_id)
        contact = await db.get(Contact, conv.contact_id)
        tenant = (await db.execute(select(Tenant).limit(1))).scalar_one()
        policy = (await db.execute(select(Policy).limit(1))).scalar_one_or_none()

        rows = (await db.execute(
            select(Message).where(Message.conversation_id == conv.id, Message.is_draft.is_(False))
            .order_by(Message.created_at.desc()).limit(HISTORY_LIMIT)
        )).scalars().all()[::-1]
        if rows and rows[-1].direction == "inbound" and rows[-1].id != message_id:
            # A burst: a newer message from the customer arrived. Its run answers everything at once.
            return AgentOutcome("skipped")

        llm = llm_factory()
        if llm is None:
            log.error("no ANTHROPIC_API_KEY: message %s left for a person", message_id)
            await _alert(db, Alert("sales", "normal", "New message; Ondra's AI isn't configured"), contact, conv)
            return AgentOutcome("no_model")

        local_time, open_now = dealer_clock(tenant)
        backend = DbToolBackend(db, contact=contact, conversation=conv,
                                price_disclosure=policy.price_disclosure if policy else "none", open_now=open_now)
        history = [Turn("customer" if m.direction == "inbound" else "assistant", m.body or "") for m in rows if m.body]
        result = await run_turn(
            llm=llm,
            backend=backend,
            dealer=DealerFacts(name=tenant.name, local_time=local_time, open_now=open_now,
                               price_disclosure=policy.price_disclosure if policy else "none",
                               handoff_triggers=list(policy.handoff_triggers) if policy else [],
                               never_say=list(policy.never_say) if policy else []),
            customer=CustomerFacts(known=not contact.display_name.startswith("+") and "@" not in contact.display_name,
                                   name=contact.display_name, language=contact.language),
            channel=conv.channel,
            history=history,
        )

        # The last gate, re-read now: a STOP may have arrived while the model was thinking.
        await db.refresh(contact)
        ok, why = may_send_outbound(contact_is_vip=contact.is_vip, contact_opted_out=await contact_opted_out(db, contact.id),
                                    author_type="ai")
        out = Message(conversation_id=conv.id, direction="outbound", author_type="ai", body=result.reply,
                      status="queued", is_draft=draft or not ok)
        db.add(out)
        await db.flush()
        # Audit: which tools ran and which checks fired. No message text in the event (PII stays in messages).
        db.add(Event(type="ai.turn", payload={
            "message_id": str(message_id), "reply_id": str(out.id), "tools": result.tools_called,
            "blocked": sorted(result.blocked), "rewritten": result.rewritten, "fallback": result.fallback,
            "model_calls": result.model_calls, "latency_ms": result.latency_ms, "draft": out.is_draft, "gate": why,
            "usage": result.usage,
        }))
        if out.is_draft:
            conv.status = "waiting_staff"
            return AgentOutcome("drafted" if ok else "blocked", result.reply, out.id,
                                int((time.monotonic() - started) * 1000), result.tools_called)
        channel = conv.channel
        to_address = (await db.execute(
            select(ContactIdentity.value).where(ContactIdentity.contact_id == contact.id,
                                                ContactIdentity.kind.in_(("phone", "whatsapp") if channel != "email" else ("email",)))
            .order_by(ContactIdentity.verified.desc()).limit(1)
        )).scalar_one()
        from_row = (await db.execute(
            select(ChannelAddress).where(ChannelAddress.channel == channel, ChannelAddress.active.is_(True)).limit(1)
        )).scalar_one()
        out_id, reply, tools = out.id, result.reply, result.tools_called

    # Send outside the transaction, then record the outcome.
    adapter = adapter_for(channel, from_row.provider)
    res = await adapter.send(OutboundMessage(channel=channel, to_address=to_address, from_address=from_row.address, body=reply))
    async with tenant_session(tenant_id) as db:
        m = await db.get(Message, out_id)
        m.status = "sent" if res.ok else "failed"
        m.provider = adapter.provider
        m.provider_message_id = res.provider_message_id
        if not res.ok:
            db.add(Event(type="message.send_failed", payload={"message_id": str(out_id), "error": res.error}))
        else:
            (await db.get(Conversation, conversation_id)).status = "waiting_customer"
    return AgentOutcome("sent" if res.ok else "send_failed", reply, out_id, int((time.monotonic() - started) * 1000), tools)


async def handle(msg: InboundMessage) -> tuple[IngestResult, AgentOutcome | None]:
    """Ingest, then run the agent if the policy allows. Used inline by tests and evals, and as the background job."""
    res = await ingest(msg)
    if res.status != "stored" or not res.run_ai:
        return res, None
    return res, await run_agent(res.tenant_id, res.conversation_id, res.message_id, res.draft)
