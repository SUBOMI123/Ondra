"""Phone calls (BUILD_PLAN.md §4.2, Step 5). The voice worker calls these; they hold the product rules for calls.

    start_call     before anyone speaks: find the dealer and the caller, open the call record, decide the route:
                   VIP -> ring the owner directly (the AI never answers); voice AI off -> ring the team; else AI.
    finish_call    store transcript, timings and outcome; queue the summary; handle a missed call.
    missed call    text back within a minute ONLY if the caller has recorded consent to texts (CLAUDE.md: no
                   automated outbound texts without recorded consent); otherwise a call-back task. Never for VIPs.
    summarize      after the call, a short summary for staff (never for VIP calls: VIPs never get AI content).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from ondra_core.channels.identity import normalize_phone
from ondra_core.models import Call, Contact, ContactIdentity, Conversation, Event, Message, Tenant, User
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.config import get_settings
from ondra_api.db import no_tenant_session, tenant_session
from ondra_api.services.agent_tools import assignee_for
from ondra_api.services.jobs import enqueue

log = logging.getLogger("ondra.calls")
Route = Literal["ai", "ring_owner", "ring_team"]


@dataclass
class CallPlan:
    tenant_id: uuid.UUID
    call_id: uuid.UUID
    conversation_id: uuid.UUID
    contact_id: uuid.UUID
    route: Route
    caller_name: str | None
    known: bool
    is_vip: bool
    dealer_name: str
    ring_number: str | None = None  # who to ring when the AI doesn't answer
    ring_user_id: uuid.UUID | None = None
    disclose_recording: bool = False
    upcoming: list = field(default_factory=list)


async def _find_tenant(to_number: str) -> uuid.UUID | None:
    async with no_tenant_session() as db:
        return (await db.execute(text("SELECT channel_find_tenant('phone', :a)"), {"a": to_number})).scalar()


async def _contact_for(db: AsyncSession, number: str) -> tuple[Contact, bool]:
    ident = (await db.execute(
        select(ContactIdentity).where(ContactIdentity.kind.in_(("phone", "whatsapp")), ContactIdentity.value == number)
        .order_by(ContactIdentity.verified.desc()).limit(1)
    )).scalar_one_or_none()
    if ident is None:
        c = Contact(display_name=number, preferred_channel="phone")
        db.add(c)
        await db.flush()
        db.add(ContactIdentity(contact_id=c.id, kind="phone", value=number))
        return c, False
    c = await db.get(Contact, ident.contact_id)
    while c.merged_into_id:
        c = await db.get(Contact, c.merged_into_id)
    return c, True


async def start_call(*, from_number: str, to_number: str, provider_call_sid: str) -> CallPlan | None:
    """Called the moment a call arrives, before the AI says anything."""
    to_n, from_n = normalize_phone(to_number), normalize_phone(from_number)
    tenant_id = await _find_tenant(to_n)
    if tenant_id is None:
        log.warning("call to a number no dealer owns")
        return None
    async with tenant_session(tenant_id) as db:
        tenant = (await db.execute(select(Tenant).limit(1))).scalar_one()
        contact, known = await _contact_for(db, from_n)
        conv = (await db.execute(select(Conversation).where(Conversation.contact_id == contact.id, Conversation.channel == "phone",
                                                            Conversation.status != "closed").limit(1))).scalar_one_or_none()
        if conv is None:
            conv = Conversation(contact_id=contact.id, channel="phone", ai_mode="auto")
            db.add(conv)
            await db.flush()
        call_id = (await db.execute(insert(Call).values(
            conversation_id=conv.id, contact_id=contact.id, provider_call_sid=provider_call_sid, direction="inbound",
            started_at=datetime.now(UTC), from_number=from_n, to_number=to_n,
        ).on_conflict_do_nothing(constraint="calls_provider_call_sid").returning(Call.id))).scalar_one_or_none()
        if call_id is None:  # the provider retried; same call
            call_id = (await db.execute(select(Call.id).where(Call.provider_call_sid == provider_call_sid))).scalar_one()
        settings = tenant.settings or {}

        route: Route = "ai"
        ring_user = None
        if contact.is_vip:
            # Product rule: a VIP's call rings the owner (or the VIP's handler) directly. The AI never speaks.
            route = "ring_owner"
            ring_user = await db.get(User, contact.vip_owner_user_id) if contact.vip_owner_user_id else None
            if ring_user is None or not ring_user.active:
                ring_user = (await db.execute(select(User).where(User.role == "owner", User.active.is_(True)).limit(1))).scalar_one_or_none()
        elif settings.get("voice_ai") is False or conv.ai_mode == "off":
            route = "ring_team"
            ring_user = await db.get(User, await assignee_for(db, "sales"))
        db.add(Event(type="call.started", payload={"call_id": str(call_id), "route": route, "vip": contact.is_vip}))
        return CallPlan(
            tenant_id=tenant_id, call_id=call_id, conversation_id=conv.id, contact_id=contact.id, route=route,
            caller_name=contact.display_name if known and not contact.display_name.startswith("+") else None,
            known=known, is_vip=contact.is_vip, dealer_name=tenant.name,
            ring_number=ring_user.phone if ring_user else None, ring_user_id=ring_user.id if ring_user else None,
            disclose_recording=settings.get("call_recording") == "with_disclosure",
        )


async def finish_call(tenant_id: uuid.UUID, call_id: uuid.UUID, *, handled_by: Literal["ai", "staff", "owner", "missed"],
                      outcome: str, transcript: list[dict] | None = None, recording_url: str | None = None,
                      recording_consent: bool = False, metrics: dict | None = None,
                      transferred_to_user_id: uuid.UUID | None = None) -> None:
    async with tenant_session(tenant_id) as db:
        call = await db.get(Call, call_id)
        now = datetime.now(UTC)
        call.ended_at = now
        call.duration_s = int((now - call.started_at).total_seconds()) if call.started_at else None
        call.handled_by, call.outcome = handled_by, outcome
        call.transcript = transcript or []
        call.recording_url = recording_url if recording_consent else None  # no recording without consent
        call.recording_consent = recording_consent
        call.metrics = metrics or {}
        call.transferred_to_user_id = transferred_to_user_id
        db.add(Event(type="call.ended", payload={"call_id": str(call.id), "handled_by": handled_by, "outcome": outcome,
                                                 "contact_id": str(call.contact_id) if call.contact_id else None,
                                                 "duration_s": call.duration_s, "latency": (metrics or {}).get("summary")}))
        contact = await db.get(Contact, call.contact_id) if call.contact_id else None
        if handled_by == "missed":
            await _missed(db, call, contact)
        elif transcript and contact is not None and not contact.is_vip:
            enqueue(db, "call_summary", {"call_id": str(call.id)})


async def _has_text_consent(db: AsyncSession, contact_id: uuid.UUID) -> bool:
    """Recorded, current opt-in for transactional texts, and no opt-out anywhere."""
    from ondra_api.services.inbound import contact_opted_out

    if await contact_opted_out(db, contact_id):
        return False
    row = (await db.execute(text("""
        SELECT status FROM consents WHERE contact_id = :c AND channel = 'sms' AND purpose = 'transactional'
        ORDER BY captured_at DESC, created_at DESC LIMIT 1
    """), {"c": contact_id})).scalar()
    return row == "opted_in"


async def _missed(db: AsyncSession, call: Call, contact: Contact | None) -> None:
    from ondra_api.services.tasks import new_task

    if contact is None:
        return
    first = contact.display_name.split()[0] if not contact.display_name.startswith("+") else "the caller"
    if contact.is_vip:
        # Plan §4.2: an unanswered VIP gets the owner alerted and a high-priority task, never an automated text.
        owner = contact.vip_owner_user_id or await assignee_for(db, "owner")
        await new_task(db, title=f"{contact.display_name}: Call {first} back (VIP)", contact_id=contact.id,
                       conversation_id=call.conversation_id, assignee_user_id=owner, source="rule", urgency="high",
                       brief="A VIP called and nobody answered.")
        db.add(Event(type="alert.created", payload={"to": "owner", "urgency": "high", "reason": "VIP call missed",
                                                    "contact_id": str(contact.id)}))
        return
    if await _has_text_consent(db, contact.id):
        # Text back through the one send path (opt-outs re-checked there). Queued now: goes out within a minute.
        sms = (await db.execute(select(Conversation).where(Conversation.contact_id == contact.id, Conversation.channel == "sms",
                                                           Conversation.status != "closed").limit(1))).scalar_one_or_none()
        if sms is None:
            sms = Conversation(contact_id=contact.id, channel="sms", ai_mode="auto")
            db.add(sms)
            await db.flush()
        tenant = (await db.execute(select(Tenant).limit(1))).scalar_one()
        m = Message(conversation_id=sms.id, direction="outbound", author_type="system", status="queued",
                    body=f"Sorry we missed your call at {tenant.name}. Reply here and we'll help, or we'll call you back shortly.")
        db.add(m)
        await db.flush()
        enqueue(db, "send_message", {"message_id": str(m.id)})
        db.add(Event(type="call.text_back", payload={"call_id": str(call.id), "message_id": str(m.id)}))
    else:
        from ondra_api.services.inbound import contact_opted_out

        reason = "opted out" if await contact_opted_out(db, contact.id) else "no recorded consent"
        db.add(Event(type="call.text_back_skipped", payload={"call_id": str(call.id), "reason": reason}))
    await new_task(db, title=f"{contact.display_name}: Call {first} back", contact_id=contact.id,
                   conversation_id=call.conversation_id, assignee_user_id=await assignee_for(db, "sales"),
                   source="rule", urgency="normal", brief="Missed call.")


async def summarize(tenant_id: uuid.UUID, payload: dict) -> str:
    """Job: a short summary for staff. Uses the fast model when configured; never for VIP calls."""
    async with tenant_session(tenant_id) as db:
        call = await db.get(Call, uuid.UUID(payload["call_id"]))
        contact = await db.get(Contact, call.contact_id) if call.contact_id else None
        if call is None or not call.transcript or (contact and contact.is_vip):
            return "skipped"
        lines = "\n".join(f"{t.get('who', '?')}: {t.get('text', '')}" for t in call.transcript)
    summary = await summarize_text(lines)
    async with tenant_session(tenant_id) as db:
        call = await db.get(Call, uuid.UUID(payload["call_id"]))
        call.summary = summary
    return "done"


async def summarize_text(lines: str) -> str:
    s = get_settings()
    if not s.anthropic_api_key:
        first = next((ln.split(": ", 1)[1] for ln in lines.splitlines() if ln.startswith("caller: ")), "")
        return f"Caller said: {first[:200]}" if first else "Call with no transcript."
    from ondra_core.agent.llm import AnthropicLLM

    llm = AnthropicLLM(api_key=s.anthropic_api_key, model=s.model_fast, effort="low", base_url=s.anthropic_api_base,
                       max_tokens=2000)
    system = [{"type": "text", "text": "Summarise this dealership phone call for the sales or service team in two or three "
                                       "plain sentences: who called, what they wanted, what was agreed or booked, and "
                                       "what the team needs to do next. No preamble."}]
    resp = await llm.create(system=system, messages=[{"role": "user", "content": lines[:20000]}], tools=[])
    return resp.text.strip() or "No summary."
