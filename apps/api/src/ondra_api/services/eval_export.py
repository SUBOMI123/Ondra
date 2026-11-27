"""Turning replies people rated wrong into draft eval cases (BUILD_PLAN.md §6.3a: "ratings feed the eval set").

    uv run python -m ondra_api.services.eval_export --tenant <id> [--out evals/candidates]

Each rated reply becomes one YAML file in the golden-case format, with the conversation up to that point, what Ondra
said, and the person's verdict and note. It's a draft: `expect` is left for a person to write (what *should* have
happened), and the file sits in `evals/candidates/`, which git ignores and the runner doesn't read. It moves into
`evals/golden/` only after someone has read it, written the expectation and checked the redaction.

Redaction, before anything is written: customer names become "the customer", phone numbers, emails, VINs and street
addresses are replaced, and the dealer's staff keep only first names. It's pattern-based and can miss things (a name
spelled oddly, an address in free text), which is why a person reviews each file before it's kept.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import uuid
from pathlib import Path

import yaml
from ondra_core.models import Contact, Conversation, Message, MessageRating, Tenant, User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.db import tenant_session

_PHONE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_VIN = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")
_STREET = re.compile(r"\b\d{1,5}\s+(?:[A-Z][a-z]+\s){1,3}(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Lane|Ln|Dr|Drive|Ct|Way)\b")


def redact(text: str, names: list[str]) -> str:
    """Addresses, emails, VINs and phone numbers first (a name inside an email would otherwise break the email
    pattern), then the customer's names."""
    out = _EMAIL.sub("[email]", text or "")
    out = _VIN.sub("[VIN]", out)
    out = _STREET.sub("[address]", out)
    out = _PHONE.sub("[phone]", out)
    for n in sorted({n for n in names if n and len(n) > 1}, key=len, reverse=True):
        out = re.sub(rf"\b{re.escape(n)}\b", "the customer", out, flags=re.IGNORECASE)
    return out


async def candidates(db: AsyncSession, *, limit: int = 100) -> list[dict]:
    tenant = (await db.execute(select(Tenant).limit(1))).scalar_one()
    staff = {u.id: u.name for u in (await db.execute(select(User))).scalars()}
    rated = (await db.execute(select(MessageRating, Message).join(Message, Message.id == MessageRating.message_id)
                              .where(MessageRating.rating.in_(("wrong", "tone"))).order_by(MessageRating.updated_at.desc()).limit(limit))).all()
    out = []
    for r, m in rated:
        conv = await db.get(Conversation, m.conversation_id)
        contact = await db.get(Contact, conv.contact_id)
        if contact.is_vip:
            continue  # Ondra never writes to VIPs; a rating here would be a mistake, not a case
        names = [contact.display_name, *contact.display_name.split()]
        earlier = (await db.execute(select(Message).where(Message.conversation_id == conv.id, Message.is_draft.is_(False),
                                                          Message.created_at <= m.created_at).order_by(Message.created_at.desc()).limit(10))).scalars().all()[::-1]
        turns, history = [], []
        for e in earlier:
            if e.id == m.id:
                break
            history.append({"from": "customer" if e.direction == "inbound" else "ondra" if e.author_type == "ai" else "staff",
                            "text": redact(e.body or "", names)})
        last_customer = next((h["text"] for h in reversed(history) if h["from"] == "customer"), None)
        if last_customer is None:
            continue
        turns.append({"customer": last_customer, "expect": {"reply": True, "must": [], "must_not": []}})
        case_id = f"cand-{str(m.id)[:8]}"
        out.append({
            "synthetic": False, "needs_review": True, "id": case_id,
            "title": f"Rated {'wrong' if r.rating == 'wrong' else 'off in tone'}: TODO name this case",
            "category": "rated", "channel": conv.channel,
            "dealer": {"local_time": m.created_at.strftime("%a %-I:%M %p").lower(), "open_now": True,
                       "policy": {"price_disclosure": "listed", "draft_mode": False}},
            "contact": {"known": False, "vip": False, "opted_out": False, "language": contact.language or "en"},
            "earlier": history[:-1] if history and history[-1]["text"] == last_customer else history,
            "turns": turns,
            "ondra_said": redact(m.body or "", names),
            "verdict": {"rating": r.rating, "by": (staff.get(r.user_id) or "").split(" ")[0] or None, "note": redact(r.note or "", names) or None},
            "notes": f"From {tenant.name}'s own conversations. TODO: write what should have happened in expect, check the redaction, "
                     "then move this file to evals/golden/ and drop needs_review.",
        })
    return out


async def export(tenant_id: uuid.UUID, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    async with tenant_session(tenant_id) as db:
        for case in await candidates(db):
            path = out_dir / f"{case['id']}.yaml"
            path.write_text(yaml.safe_dump(case, sort_keys=False, allow_unicode=True, width=110))
            written.append(path)
    return written


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--tenant", required=True)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[4] / "evals" / "candidates"))
    a = ap.parse_args()
    for p in asyncio.run(export(uuid.UUID(a.tenant), Path(a.out))):
        print(p)
