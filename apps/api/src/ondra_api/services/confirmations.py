"""Booking confirmations (docs/PLAN.md item 4).

When a booking is made, moved or cancelled, the customer hears about it:

    main     on their channel (where they booked, else their preferred one): WhatsApp, text or email. Skipped for a
             new booking made by Ondra in a written conversation: its reply there already confirmed it.
    email    a copy whenever we have their email (and the main one wasn't email), with a calendar invite (.ics).

At most those two messages per change. Every message carries one link to the booking's own page (`/b?t=<token>`), where
they add it to Apple, Google or Outlook calendar, move it or cancel it.

The same rules as every automated message (`may_send`): nothing to someone who opted out, nothing automated to a VIP
(their person gets a task to confirm personally instead), no text without recorded consent, and WhatsApp only inside
WhatsApp's 24-hour window (outside it a Meta-approved template is needed; not set up yet). Anything not sent is
recorded on the appointment with the reason, so staff see "No confirmation text: no consent on file".

Quiet hours: a change made between 8 pm and 8 am, dealer time, is confirmed at 8 am.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import uuid
from datetime import UTC, datetime, time, timedelta
from urllib.parse import quote, urlencode

from ondra_core.models import (
    Appointment,
    AppointmentType,
    Contact,
    ContactIdentity,
    Conversation,
    Event,
    Message,
    Tenant,
    User,
)
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.config import get_settings
from ondra_api.db import tenant_session
from ondra_api.services.booking import LIVE, tz_of
from ondra_api.services.jobs import enqueue

QUIET_START, QUIET_END = time(20, 0), time(8, 0)
WHATSAPP_WINDOW = timedelta(hours=24)
WRITTEN = ("sms", "whatsapp", "email")


# --- the booking's own link ----------------------------------------------------------------------------------------

def _sign(raw: bytes) -> str:
    return base64.urlsafe_b64encode(hmac.new(get_settings().jwt_secret.encode(), b"booking:" + raw, hashlib.sha256).digest()[:16]).decode().rstrip("=")


def manage_token(tenant_id: uuid.UUID, appointment_id: uuid.UUID) -> str:
    """Names the dealer and the booking, signed so it can't be guessed or altered. Anyone with the link can see,
    move or cancel that one booking (like the links every booking system sends), nothing else."""
    raw = tenant_id.bytes + appointment_id.bytes
    return base64.urlsafe_b64encode(raw).decode().rstrip("=") + "." + _sign(raw)


def read_token(token: str) -> tuple[uuid.UUID, uuid.UUID] | None:
    try:
        body, sig = token.split(".", 1)
        raw = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
    except ValueError:
        return None
    if len(raw) != 32 or not hmac.compare_digest(sig, _sign(raw)):
        return None
    return uuid.UUID(bytes=raw[:16]), uuid.UUID(bytes=raw[16:])


def manage_url(tenant_id: uuid.UUID, appointment_id: uuid.UUID) -> str:
    return f"{get_settings().app_base_url.rstrip('/')}/b?t={manage_token(tenant_id, appointment_id)}"


# --- the calendar invite -------------------------------------------------------------------------------------------

def _ics_time(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _ics_text(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    """RFC 5545 3.1: lines longer than 75 octets are folded with CRLF and a space."""
    out, raw = [], line.encode()
    while len(raw) > 75:
        cut = 75
        while cut > 0 and (raw[cut] & 0xC0) == 0x80:  # don't split a UTF-8 character
            cut -= 1
        out.append(raw[:cut].decode())
        raw = b" " + raw[cut:]
    out.append(raw.decode())
    return "\r\n".join(out)


def event_title(tenant: Tenant, t: AppointmentType) -> str:
    return f"{t.name} at {tenant.name}"


def ics(tenant: Tenant, a: Appointment, t: AppointmentType, *, cancelled: bool = False, sequence: int = 0, url: str = "") -> str:
    """One VEVENT, the same UID for the life of the booking so a move updates it and a cancellation removes it
    (METHOD REQUEST / CANCEL, RFC 5546)."""
    address = (tenant.settings or {}).get("address") or tenant.name
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Ondra//Bookings//EN", "CALSCALE:GREGORIAN",
        f"METHOD:{'CANCEL' if cancelled else 'REQUEST'}",
        "BEGIN:VEVENT",
        f"UID:{a.id}@ondra",
        f"SEQUENCE:{sequence}",
        f"DTSTAMP:{_ics_time(datetime.now(UTC))}",
        f"DTSTART:{_ics_time(a.starts_at)}",
        f"DTEND:{_ics_time(a.ends_at)}",
        f"SUMMARY:{_ics_text(event_title(tenant, t))}",
        f"LOCATION:{_ics_text(address)}",
        f"DESCRIPTION:{_ics_text(f'To move or cancel: {url}' if url else '')}",
        f"STATUS:{'CANCELLED' if cancelled else 'CONFIRMED'}",
        "END:VEVENT", "END:VCALENDAR",
    ]
    if url:
        lines.insert(-2, f"URL:{url}")
    return "\r\n".join(_fold(x) for x in lines) + "\r\n"


def calendar_links(tenant: Tenant, a: Appointment, t: AppointmentType, url: str) -> dict:
    """"Add to calendar" for Google and Outlook (their add-event pages), and the .ics for Apple and everything else.
    TODO(verify): the Google (calendar/render?action=TEMPLATE) and Outlook (deeplink/compose) parameters are the
    widely used ones, not from a page either company maintains for this; check both open prefilled before launch."""
    title, where = event_title(tenant, t), (tenant.settings or {}).get("address") or tenant.name
    details = f"To move or cancel: {url}"
    google = "https://calendar.google.com/calendar/render?" + urlencode(
        {"action": "TEMPLATE", "text": title, "dates": f"{_ics_time(a.starts_at)}/{_ics_time(a.ends_at)}", "details": details,
         "location": where}, quote_via=quote)
    outlook = "https://outlook.live.com/calendar/0/deeplink/compose?" + urlencode(
        {"path": "/calendar/action/compose", "rru": "addevent", "subject": title, "startdt": a.starts_at.astimezone(UTC).isoformat(),
         "enddt": a.ends_at.astimezone(UTC).isoformat(), "body": details, "location": where}, quote_via=quote)
    return {"google": google, "outlook": outlook}


# --- who may be sent what ------------------------------------------------------------------------------------------

async def may_send(db: AsyncSession, contact: Contact, channel: str, now: datetime | None = None) -> tuple[bool, str]:
    """The rules for an automated message to a customer (confirmations, reminders). Returns (ok, why not)."""
    from ondra_api.services.inbound import contact_opted_out

    if await contact_opted_out(db, contact.id):
        return False, "they opted out"
    if contact.is_vip:
        return False, "VIPs are confirmed by their person, never automatically"
    if channel == "sms":
        row = (await db.execute(text("""
            SELECT status FROM consents WHERE contact_id = :c AND channel = 'sms' AND purpose = 'transactional'
            ORDER BY captured_at DESC, created_at DESC LIMIT 1"""), {"c": contact.id})).scalar()
        return (True, "") if row == "opted_in" else (False, "no consent to texts on file")
    if channel == "whatsapp":
        last_in = (await db.execute(text("""
            SELECT max(m.created_at) FROM messages m JOIN conversations c ON c.id = m.conversation_id
            WHERE c.contact_id = :c AND c.channel = 'whatsapp' AND m.direction = 'inbound'"""), {"c": contact.id})).scalar()
        if last_in is None or (now or datetime.now(UTC)) - last_in > WHATSAPP_WINDOW:
            return False, "outside WhatsApp's 24-hour window (needs an approved template)"
        return True, ""
    return True, ""


async def _address(db: AsyncSession, contact: Contact, channel: str) -> str | None:
    kinds = ("email",) if channel == "email" else ("phone", "whatsapp")
    return (await db.execute(select(ContactIdentity.value).where(ContactIdentity.contact_id == contact.id, ContactIdentity.kind.in_(kinds))
                             .limit(1))).scalar_one_or_none()


def quiet_until(tenant: Tenant, now: datetime) -> datetime | None:
    """8 am dealer time if `now` falls in quiet hours (8 pm to 8 am), else None."""
    local = now.astimezone(tz_of(tenant))
    if QUIET_END <= local.time() < QUIET_START:
        return None
    day = local.date() + (timedelta(days=1) if local.time() >= QUIET_START else timedelta())
    return datetime.combine(day, QUIET_END, tz_of(tenant)).astimezone(UTC)


# --- scheduling and sending ----------------------------------------------------------------------------------------

def schedule(db: AsyncSession, tenant: Tenant, a: Appointment, kind: str, by: str) -> None:
    """Queue the confirmation for a booking ("booked"), a move ("moved") or a cancellation ("cancelled")."""
    now = datetime.now(UTC)
    enqueue(db, "appointment_confirmation", {"appointment_id": str(a.id), "kind": kind, "by": by,
                                             "starts_at": a.starts_at.isoformat()}, run_at=quiet_until(tenant, now) or now)


def _when(tenant: Tenant, a: Appointment) -> str:
    s = a.starts_at.astimezone(tz_of(tenant))
    clock = s.strftime("%-I:%M %p").replace("AM", "am").replace("PM", "pm").replace(":00 ", " ")
    return f"{s.strftime('%A, %B %-d')} at {clock}"


def _wording(tenant: Tenant, a: Appointment, t: AppointmentType, who: str | None, kind: str, url: str) -> tuple[str, str]:
    """(subject, body). Plain, short, one link."""
    what = t.name.lower()
    with_ = f" with {who}" if who and t.category != "service" else ""
    if kind == "cancelled":
        return (f"Cancelled: your {what} at {tenant.name}",
                f"Your {what} at {tenant.name} on {_when(tenant, a)} is cancelled. To book another time, reply here.")
    lead = "Moved" if kind == "moved" else "Booked"
    return (f"{lead}: your {what} at {tenant.name}, {_when(tenant, a)}",
            (f"{lead}: your {what} at {tenant.name}, {_when(tenant, a)}{with_}. "
             f"Add it to your calendar, move it or cancel: {url}"))


async def _conversation(db: AsyncSession, contact: Contact, channel: str) -> Conversation:
    conv = (await db.execute(select(Conversation).where(Conversation.contact_id == contact.id, Conversation.channel == channel,
                                                        Conversation.status != "closed").order_by(Conversation.updated_at.desc()).limit(1))).scalar_one_or_none()
    if conv is None:
        conv = Conversation(contact_id=contact.id, channel=channel, ai_mode="auto")
        db.add(conv)
        await db.flush()
    return conv


async def send(tenant_id: uuid.UUID, payload: dict) -> str:
    """Job handler. Returns what happened, per channel (for tests and logs)."""
    from ondra_api.services.outbound import Blocked, deliver
    from ondra_api.services.tasks import new_task

    kind = payload["kind"]
    queued: list[uuid.UUID] = []
    record: dict = {"kind": kind, "at": datetime.now(UTC).isoformat(), "sent": [], "not_sent": []}
    async with tenant_session(tenant_id) as db:
        a = await db.get(Appointment, uuid.UUID(payload["appointment_id"]))
        if a is None:
            return "skipped: gone"
        if kind != "cancelled" and (a.status not in LIVE or a.starts_at.isoformat() != payload["starts_at"]):
            return "skipped: changed since"  # a later change queued its own confirmation
        if any(c.get("kind") == kind and c.get("starts_at") == payload["starts_at"] for c in a.confirmations or []):
            return "skipped: already done"
        record["starts_at"] = payload["starts_at"]
        tenant = (await db.execute(select(Tenant).limit(1))).scalar_one()
        t = await db.get(AppointmentType, a.appointment_type_id)
        contact = await db.get(Contact, a.contact_id)
        person = await db.get(User, a.assigned_user_id) if a.assigned_user_id else None
        first = contact.display_name.split()[0]

        if contact.is_vip:
            # Never automatic for a VIP: their person confirms it themselves.
            who = contact.vip_owner_user_id or (person.id if person else None)
            verb = {"booked": "Confirm", "moved": "Confirm the new time for", "cancelled": "Let them know you've cancelled"}[kind]
            task = await new_task(db, title=f"{contact.display_name}: {verb} {first}'s {t.name.lower()} personally (VIP)", contact_id=contact.id,
                                  assignee_user_id=who, source="rule", urgency="high",
                                  brief=f"{t.name}, {_when(tenant, a)}. VIPs aren't sent automatic confirmations; a call or a message from you instead.")
            record["vip_task"] = str(task.id)
            a.confirmations = [*(a.confirmations or []), record]
            return "vip: task for their person"

        url = manage_url(tenant_id, a.id)
        subject, body = _wording(tenant, a, t, person.name.split()[0] if person else None, kind, url)
        booked_in = await db.get(Conversation, a.conversation_id) if a.conversation_id else None
        # Main channel: where they booked, if written; else their preferred one; else text.
        main = booked_in.channel if booked_in and booked_in.channel in WRITTEN else (
            contact.preferred_channel if contact.preferred_channel in WRITTEN else "sms")
        if kind == "booked" and a.source == "ai" and booked_in is not None and booked_in.channel in WRITTEN:
            record["not_sent"].append({"channel": main, "why": "Ondra confirmed it in the conversation"})
            main = None
        sequence = sum(1 for c in a.confirmations or [] if c.get("kind") in ("moved", "cancelled")) + (kind != "booked")
        invite = ics(tenant, a, t, cancelled=kind == "cancelled", sequence=sequence, url=url)

        channels = [c for c in (main, "email") if c] if main != "email" else ["email"]
        for ch in dict.fromkeys(channels):
            ok, why = await may_send(db, contact, ch)
            if ok and await _address(db, contact, ch) is None:
                ok, why = False, f"no {'email address' if ch == 'email' else 'mobile number'} on file"
            if not ok:
                if ch != "email" or main == "email":  # a missing email copy isn't news; a missing main message is
                    record["not_sent"].append({"channel": ch, "why": why})
                continue
            conv = await _conversation(db, contact, ch)
            m = Message(conversation_id=conv.id, direction="outbound", author_type="system", status="queued", body=body,
                        meta={"subject": subject, "kind": f"appointment.{kind}", "appointment_id": str(a.id)})
            if ch == "email":
                m.attachments = [{"name": "invite.ics", "content_type": f"text/calendar; method={'CANCEL' if kind == 'cancelled' else 'REQUEST'}",
                                  "content_b64": base64.b64encode(invite.encode()).decode()}]
            db.add(m)
            await db.flush()
            queued.append(m.id)
            record["sent"].append({"channel": ch, "message_id": str(m.id)})
        db.add(Event(type="appointment.confirmation", payload={"appointment_id": str(a.id), "kind": kind,
                                                                "sent": [s["channel"] for s in record["sent"]],
                                                                "not_sent": record["not_sent"]}))
        a.confirmations = [*(a.confirmations or []), record]
    results = []
    for mid in queued:
        try:
            d = await deliver(tenant_id, mid)
            results.append("sent" if d.ok else f"failed: {d.error}")
        except Blocked as b:
            results.append(f"blocked: {b.reason}")
    return ", ".join(results) or "nothing sent"


def summary(a: Appointment) -> list[str]:
    """For staff, in words: what the customer was told about this booking, and why anything wasn't sent."""
    names = {"sms": "text", "whatsapp": "WhatsApp", "email": "email"}
    lines = []
    for c in a.confirmations or []:
        what = {"booked": "Confirmation", "moved": "New time", "cancelled": "Cancellation"}.get(c.get("kind"), "Message")
        if c.get("vip_task"):
            lines.append(f"{what}: their person was asked to tell them personally (VIP).")
            continue
        sent = [names.get(s["channel"], s["channel"]) for s in c.get("sent", [])]
        if sent:
            lines.append(f"{what} sent by {' and '.join(sent)}.")
        for n in c.get("not_sent", []):
            lines.append(f"No {what.lower()} by {names.get(n['channel'], n['channel'])}: {n['why']}.")
    return lines
