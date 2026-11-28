"""When a VIP calls: their person's phone rings, and if nobody answers, a fixed message in the dealer's own words.
Never the AI (CLAUDE.md product rule). docs/PLAN.md item 3.

    start    <Dial> their person (RING_SECONDS), action=/dialed. No person with a mobile: straight to the message.
    dialed   DialCallStatus completed: answered by their person, done. Anything else: the call is missed (their
             person is alerted at once and gets a high-priority call-back task, services/calls._missed), then the
             message plays inside a <Gather numDigits=1>: press 1 for the backup number, press 2 for a booking link.
    choice   1: <Dial> the backup number, action=/backup.  2: one fixed text with the dealer's booking link, sent
             through the normal send path (opt-outs re-checked there). Anything else: goodbye.
    backup   who picked up at the backup number is recorded on the call.

Press 1 is offered only when the dealer has set a backup number; press 2 only when they've set a booking link AND
the caller has recorded consent to texts (until counsel says pressing 2 is consent in itself). The backup must be a
phone a person answers, never the dealer's main line: that forwards to Ondra, and a VIP would reach the AI.

How the call gets here: the voice worker transfers a VIP's call to the VIP desk instead of straight to their person
(`desk_target`). TODO(verify): Twilio's docs couldn't be reached from the build machine (2026-11-28). Check that an
Elastic SIP trunk REFER may target a Programmable Voice SIP domain URI (sip:vip-<call>@<domain>.sip.twilio.com), and
that its Voice URL then receives the user part. Until checked, FEATURE_VIP_DESK stays off and VIP calls keep the
cold transfer straight to their person (no message on no answer). The <Dial>/<Gather> details used here are the ones
already verified for the call-back bridge (services/bridge.py).
"""

from __future__ import annotations

import uuid
from xml.sax.saxutils import escape, quoteattr

from ondra_core.models import Call, Contact, Conversation, Event, Message, Tenant, User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.config import get_settings

RING_SECONDS = 20
BACKUP_RING_SECONDS = 25
GATHER_SECONDS = 6


def settings_of(tenant: Tenant) -> dict:
    s = (tenant.settings or {}).get("vip_calls") or {}
    return {"message": s.get("message") or None, "backup_number": s.get("backup_number") or None,
            "booking_link": s.get("booking_link") or None}


def webhook_base(tenant_id: uuid.UUID, call_id: uuid.UUID) -> str:
    return f"{get_settings().public_api_url.rstrip('/')}/webhooks/voice/vip/{tenant_id}/{call_id}"


def desk_target(tenant_id: uuid.UUID, call_id: uuid.UUID) -> str | None:
    """Where the voice worker sends a VIP's call, or None to ring their person directly (the desk is off). The SIP
    domain has one Voice URL (/webhooks/voice/vip/start), so the dealer and the call travel in the address."""
    s = get_settings()
    if not s.feature_vip_desk or not s.vip_desk_sip_domain:
        return None
    return f"sip:vip-{tenant_id}_{call_id}@{s.vip_desk_sip_domain}"


def parse_target(to: str) -> tuple[uuid.UUID, uuid.UUID] | None:
    """Back from the address Twilio posts as `To` (sip:vip-<tenant>_<call>@domain)."""
    try:
        user = to.split(":", 1)[-1].split("@", 1)[0]
        tenant, call = user.removeprefix("vip-").split("_", 1)
        return uuid.UUID(tenant), uuid.UUID(call)
    except ValueError:
        return None


async def person_for(db: AsyncSession, contact: Contact) -> User | None:
    """Their person, if active with a mobile. Nobody: the message plays at once (the backup is press 1)."""
    u = await db.get(User, contact.vip_owner_user_id) if contact.vip_owner_user_id else None
    return u if u is not None and u.active and u.phone else None


async def can_text(db: AsyncSession, contact: Contact) -> bool:
    from ondra_api.services.calls import _has_text_consent

    return await _has_text_consent(db, contact.id)


def message(tenant: Tenant, contact: Contact, person: User | None, *, backup: bool, booking: bool) -> str:
    """The dealer's own words, or the default. The options are added only when they can actually happen."""
    s = settings_of(tenant)
    first = contact.display_name.split()[0] if not contact.display_name.startswith("+") else ""
    who = person.name.split()[0] if person else "Someone from our team"
    base = (s["message"] or "Sorry we missed you{comma}{first}. {person} has been told and will call you back shortly.")
    text = base.replace("{comma}", ", " if first else "").replace("{first}", first).replace("{person}", who).replace("{dealer}", tenant.name)
    if backup:
        text += " If it's urgent, press 1."
    if booking:
        text += " To book a time yourself, press 2 and we'll text you a link."
    return text


# --- TwiML --------------------------------------------------------------------------------------------------------

def _doc(body: str) -> str:
    return f'<?xml version="1.0" encoding="UTF-8"?><Response>{body}</Response>'


def ring(base: str, number: str, caller_id: str, step: str = "dialed", seconds: int = RING_SECONDS) -> str:
    return _doc(f'<Dial callerId={quoteattr(caller_id)} timeout="{seconds}" action={quoteattr(f"{base}/{step}")}>'
                f"<Number>{escape(number)}</Number></Dial>")


def offer(base: str, text: str, has_options: bool) -> str:
    if not has_options:
        return _doc(f"<Say>{escape(text)}</Say><Hangup/>")
    return _doc(f'<Gather numDigits="1" timeout="{GATHER_SECONDS}" action={quoteattr(base + "/choice")}><Say>{escape(text)}</Say></Gather>'
                "<Say>Goodbye.</Say><Hangup/>")


def goodbye(text: str = "Goodbye.") -> str:
    return _doc(f"<Say>{escape(text)}</Say><Hangup/>" if text else "<Hangup/>")


# --- what happens at each step -------------------------------------------------------------------------------------

async def send_booking_link(db: AsyncSession, tenant: Tenant, contact: Contact, link: str) -> Message:
    """One fixed text (not written by Ondra), through the one send path, so opt-outs are checked again there."""
    from ondra_api.services.jobs import enqueue

    sms = (await db.execute(select(Conversation).where(Conversation.contact_id == contact.id, Conversation.channel == "sms",
                                                       Conversation.status != "closed").limit(1))).scalar_one_or_none()
    if sms is None:
        sms = Conversation(contact_id=contact.id, channel="sms", ai_mode="off")  # a VIP's thread: never the AI
        db.add(sms)
        await db.flush()
    m = Message(conversation_id=sms.id, direction="outbound", author_type="system", status="queued",
                body=f"{tenant.name}: book a time that suits you here: {link}")
    db.add(m)
    await db.flush()
    enqueue(db, "send_message", {"message_id": str(m.id)})
    return m


async def note(db: AsyncSession, call: Call, **vip) -> None:
    call.metrics = {**(call.metrics or {}), "vip_desk": {**((call.metrics or {}).get("vip_desk") or {}), **vip}}
    db.add(Event(type="call.vip_desk", payload={"call_id": str(call.id), **vip}))
