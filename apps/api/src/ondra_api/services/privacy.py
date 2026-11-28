"""A customer's right to their data: export everything held about one client, or erase it (security audit,
2026-11-28; CCPA/GDPR-style requests). Admins only, both audited by the router.

Erase anonymises rather than deletes rows: the dealership's counts (leads, bookings, reply times) stay true, but
nothing left says who the person was. Kept on purpose:
- consent records (status, channel, when), without their evidence: proof the dealer honoured an opt-out;
- if they opted out, their phone and email stay attached to the erased record, so a STOP keeps working if they
  ever write again. Nothing else is kept for an opted-in client;
- the audit log, which is append-only (the app role can't change it); it holds names only where staff renamed a
  client. TODO(verify, counsel): whether that's acceptable, or the audit entries need a separate redaction step.
"""

from __future__ import annotations

import uuid
from typing import Any

from ondra_core.models import (
    Appointment,
    Call,
    Consent,
    Contact,
    ContactIdentity,
    Conversation,
    Deal,
    Message,
    Task,
)
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

ERASED_NAME = "Erased client"


def _row(obj: Any, *skip: str) -> dict:
    return {c.key: getattr(obj, c.key) for c in obj.__mapper__.column_attrs if c.key not in ("tenant_id", *skip)}


async def export(db: AsyncSession, contact: Contact) -> dict:
    """Everything held about this client, as plain data."""
    cid = contact.id
    convs = (await db.execute(select(Conversation).where(Conversation.contact_id == cid))).scalars().all()
    conv_ids = [c.id for c in convs]
    messages = (await db.execute(select(Message).where(Message.conversation_id.in_(conv_ids)).order_by(Message.created_at))
                ).scalars().all() if conv_ids else []
    return {
        "client": _row(contact),
        "phone_numbers_and_emails": [_row(i) for i in (await db.execute(select(ContactIdentity).where(ContactIdentity.contact_id == cid))).scalars()],
        "consents": [_row(c) for c in (await db.execute(select(Consent).where(Consent.contact_id == cid).order_by(Consent.captured_at))).scalars()],
        "conversations": [{**_row(c), "messages": [_row(m) for m in messages if m.conversation_id == c.id]} for c in convs],
        "calls": [_row(c, "metrics") for c in (await db.execute(select(Call).where(Call.contact_id == cid))).scalars()],
        "appointments": [_row(a) for a in (await db.execute(select(Appointment).where(Appointment.contact_id == cid))).scalars()],
        "deals": [_row(d) for d in (await db.execute(select(Deal).where(Deal.contact_id == cid))).scalars()],
        "tasks": [_row(t) for t in (await db.execute(select(Task).where(Task.contact_id == cid))).scalars()],
    }


async def erase(db: AsyncSession, contact: Contact, *, opted_out: bool) -> dict:
    """Anonymise this client everywhere. Returns what was changed, for the audit record."""
    p = {"c": contact.id}
    convs = "(SELECT id FROM conversations WHERE contact_id = :c)"
    done = {
        "messages": (await db.execute(text(f"""UPDATE messages SET body = '[erased]', attachments = '[]'::jsonb,
            meta = '{{}}'::jsonb WHERE conversation_id IN {convs}"""), p)).rowcount,
        "calls": (await db.execute(text("""UPDATE calls SET transcript = '[]'::jsonb, summary = NULL, recording_url = NULL,
            from_number = NULL WHERE contact_id = :c"""), p)).rowcount,
        "appointments": (await db.execute(text("""UPDATE appointments SET details = '{}'::jsonb, vin = NULL
            WHERE contact_id = :c"""), p)).rowcount,
        "deals": (await db.execute(text("""UPDATE deals SET vehicle_of_interest = '{}'::jsonb, timeline = NULL,
            destination = NULL WHERE contact_id = :c"""), p)).rowcount,
        "tasks": (await db.execute(text(f"""UPDATE tasks SET title = '{ERASED_NAME}', brief = NULL
            WHERE contact_id = :c"""), p)).rowcount,
        "consents": (await db.execute(text("UPDATE consents SET evidence = '{}'::jsonb WHERE contact_id = :c"), p)).rowcount,
        # Events record names only when staff renamed someone.
        "events": (await db.execute(text("""UPDATE events SET payload = payload - 'from' - 'to'
            WHERE type = 'contact.renamed' AND payload->>'contact_id' = :cs"""), {"cs": str(contact.id)})).rowcount,
    }
    if not opted_out:
        done["identities"] = (await db.execute(text("DELETE FROM contact_identities WHERE contact_id = :c"), p)).rowcount
    contact.display_name, contact.name_source = ERASED_NAME, None
    contact.notes, contact.tags, contact.language, contact.preferred_channel = None, [], None, None
    await db.flush()
    return done


__all__ = ["ERASED_NAME", "erase", "export", "uuid"]
