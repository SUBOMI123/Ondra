"""What Ondra knows (BUILD_PLAN.md §6.3a): the questions it couldn't answer, the dealer's answers, and what people
made of its replies. Anyone signed in can read; owners, admins and managers can answer (they know the answers);
anyone who can reply to customers can rate a reply. Changes to answers are audited."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from ondra_core.models import AuditLog, Contact, Conversation, Event, KnowledgeDoc, KnowledgeGap, Message, MessageRating, User
from ondra_core.permissions import Perm, can_see_vips, has_perm
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.deps import Caller, get_db, require
from ondra_api.services.learning import answer_gap, save_doc

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
ratings_router = APIRouter(tags=["knowledge"])


class AnswerIn(BaseModel):
    question: str = Field(min_length=3, max_length=300)  # the question as the dealer would word it
    answer: str = Field(min_length=3, max_length=4000)


class RatingIn(BaseModel):
    rating: Literal["good", "wrong", "tone"]
    note: str | None = Field(None, max_length=1000)


def _audit(db: AsyncSession, caller: Caller, request: Request, action: str, resource: str, before, after) -> None:
    db.add(AuditLog(actor_type="user", actor_user_id=caller.user_id, action=action, resource=resource,
                    before=before, after=after, ip=request.client.host if request.client else None))


def _doc(d: KnowledgeDoc) -> dict:
    return {"id": str(d.id), "question": d.title, "answer": d.body, "updated_at": d.updated_at.isoformat()}


def _clean(body: AnswerIn) -> tuple[str, str]:
    q, a = body.question.strip(), body.answer.strip()
    if len(q) < 3 or len(a) < 3:
        raise HTTPException(422, "Write both the question and the answer.")
    return q, a


async def _asked(db: AsyncSession, caller: Caller, gap: KnowledgeGap) -> str | None:
    """A customer's own words for this gap: their last message in the most recent conversation that raised it.
    Never a VIP's words to someone who can't see VIPs."""
    for conv_id in reversed(gap.example_conversation_ids or []):
        conv = await db.get(Conversation, conv_id)
        if conv is None:
            continue
        contact = await db.get(Contact, conv.contact_id)
        if contact is None or (contact.is_vip and not can_see_vips(caller.role) and contact.vip_owner_user_id != caller.user_id):
            continue
        body = (await db.execute(select(Message.body).where(Message.conversation_id == conv_id, Message.direction == "inbound")
                                 .order_by(Message.created_at.desc()).limit(1))).scalar_one_or_none()
        if body:
            return body[:400]
    return None


@router.get("")
async def get_knowledge(ctx: tuple[Caller, AsyncSession] = Depends(get_db)) -> dict:
    caller, db = ctx
    gaps = (await db.execute(select(KnowledgeGap).where(KnowledgeGap.status == "open")
                             .order_by(KnowledgeGap.occurrences.desc(), KnowledgeGap.last_asked_at.desc()).limit(100))).scalars().all()
    docs = (await db.execute(select(KnowledgeDoc).order_by(KnowledgeDoc.updated_at.desc()).limit(500))).scalars().all()
    ignored = (await db.execute(select(func.count()).select_from(KnowledgeGap).where(KnowledgeGap.status == "ignored"))).scalar_one()
    return {
        "unanswered": [{"id": str(g.id), "question": g.question, "times": g.occurrences, "last_asked_at": g.last_asked_at.isoformat(),
                        "asked": await _asked(db, caller, g)} for g in gaps],
        "answers": [_doc(d) for d in docs],
        "ignored": ignored,
        "can_edit": has_perm(caller.role, Perm.KNOWLEDGE_WRITE),
    }


@router.post("/unanswered/{gap_id}/answer", status_code=201)
async def answer(gap_id: uuid.UUID, body: AnswerIn, request: Request,
                 ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.KNOWLEDGE_WRITE))) -> dict:
    """Answer it once: it becomes something Ondra knows, from the next message on."""
    caller, db = ctx
    gap = await db.get(KnowledgeGap, gap_id)
    if gap is None or gap.status != "open":
        raise HTTPException(404, "That question isn't waiting for an answer.")
    q, a = _clean(body)
    doc = await answer_gap(db, gap, title=q, answer=a, user_id=caller.user_id)
    _audit(db, caller, request, "knowledge.answer", f"knowledge_gap:{gap.id}", {"question": gap.question}, _doc(doc))
    return _doc(doc)


@router.post("/unanswered/{gap_id}/ignore", status_code=204)
async def ignore(gap_id: uuid.UUID, request: Request,
                 ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.KNOWLEDGE_WRITE))) -> None:
    """Not something Ondra should answer (a person always handles it). It leaves the list; asked again, it stays off."""
    caller, db = ctx
    gap = await db.get(KnowledgeGap, gap_id)
    if gap is None or gap.status != "open":
        raise HTTPException(404, "That question isn't waiting for an answer.")
    gap.status = "ignored"
    _audit(db, caller, request, "knowledge.ignore", f"knowledge_gap:{gap.id}", {"question": gap.question}, None)


@router.post("/unanswered/{gap_id}/reopen", status_code=204)
async def reopen(gap_id: uuid.UUID, ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.KNOWLEDGE_WRITE))) -> None:
    _caller, db = ctx
    gap = await db.get(KnowledgeGap, gap_id)
    if gap is None or gap.status != "ignored":
        raise HTTPException(404)
    gap.status = "open"


@router.post("/answers", status_code=201)
async def add_answer(body: AnswerIn, request: Request,
                     ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.KNOWLEDGE_WRITE))) -> dict:
    caller, db = ctx
    q, a = _clean(body)
    doc = await save_doc(db, title=q, body=a, user_id=caller.user_id)
    _audit(db, caller, request, "knowledge.add", f"knowledge_doc:{doc.id}", None, _doc(doc))
    return _doc(doc)


@router.put("/answers/{doc_id}")
async def change_answer(doc_id: uuid.UUID, body: AnswerIn, request: Request,
                        ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.KNOWLEDGE_WRITE))) -> dict:
    caller, db = ctx
    doc = await db.get(KnowledgeDoc, doc_id)
    if doc is None:
        raise HTTPException(404)
    before = _doc(doc)
    q, a = _clean(body)
    doc = await save_doc(db, title=q, body=a, user_id=caller.user_id, doc=doc)
    _audit(db, caller, request, "knowledge.update", f"knowledge_doc:{doc.id}", before, _doc(doc))
    return _doc(doc)


@router.delete("/answers/{doc_id}", status_code=204)
async def delete_answer(doc_id: uuid.UUID, request: Request,
                        ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.KNOWLEDGE_WRITE))) -> None:
    caller, db = ctx
    doc = await db.get(KnowledgeDoc, doc_id)
    if doc is None:
        raise HTTPException(404)
    _audit(db, caller, request, "knowledge.delete", f"knowledge_doc:{doc.id}", _doc(doc), None)
    await db.delete(doc)


@router.get("/corrections")
async def corrections(limit: int = 50, ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.KNOWLEDGE_WRITE))) -> dict:
    """Where people corrected Ondra: drafts they changed before sending, and replies they rated wrong or off in
    tone. Each can be turned into an answer. VIP conversations are left out: Ondra never writes to VIPs."""
    _caller, db = ctx
    limit = max(1, min(limit, 200))
    edits = (await db.execute(select(Event).where(Event.type == "draft.edited").order_by(Event.occurred_at.desc()).limit(limit))).scalars().all()
    rated = (await db.execute(
        select(MessageRating, Message, User.name).join(Message, Message.id == MessageRating.message_id)
        .join(User, User.id == MessageRating.user_id).where(MessageRating.rating.in_(("wrong", "tone")))
        .order_by(MessageRating.updated_at.desc()).limit(limit))).all()

    async def asked_before(m: Message) -> str | None:
        return (await db.execute(select(Message.body).where(
            Message.conversation_id == m.conversation_id, Message.direction == "inbound", Message.created_at < m.created_at)
            .order_by(Message.created_at.desc()).limit(1))).scalar_one_or_none()

    return {
        "edits": [{"message_id": e.payload.get("message_id"), "before": e.payload.get("before"), "after": e.payload.get("after"),
                   "at": e.occurred_at.isoformat()} for e in edits],
        "rated": [{"message_id": str(m.id), "rating": r.rating, "note": r.note, "by": name, "reply": m.body,
                   "customer_said": await asked_before(m), "at": r.updated_at.isoformat()} for r, m, name in rated],
        "good": (await db.execute(select(func.count()).select_from(MessageRating).where(MessageRating.rating == "good"))).scalar_one(),
    }


# --- rating a reply (from the Inbox) -----------------------------------------------------------------------------

async def _ai_message(db: AsyncSession, message_id: uuid.UUID) -> Message:
    m = await db.get(Message, message_id)
    if m is None or m.author_type != "ai" or m.is_draft:
        raise HTTPException(404, "Only replies Ondra sent can be rated.")
    return m


@ratings_router.put("/messages/{message_id}/rating")
async def rate(message_id: uuid.UUID, body: RatingIn,
               ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONVERSATIONS_REPLY))) -> dict:
    caller, db = ctx
    m = await _ai_message(db, message_id)
    r = (await db.execute(select(MessageRating).where(MessageRating.message_id == m.id))).scalar_one_or_none()
    if r is None:
        r = MessageRating(message_id=m.id, user_id=caller.user_id, rating=body.rating)
        db.add(r)
    r.user_id, r.rating, r.note = caller.user_id, body.rating, (body.note or "").strip() or None
    db.add(Event(type="reply.rated", payload={"message_id": str(m.id), "rating": body.rating, "by": str(caller.user_id)}))
    await db.flush()
    return {"message_id": str(m.id), "rating": r.rating, "note": r.note}


@ratings_router.delete("/messages/{message_id}/rating", status_code=204)
async def unrate(message_id: uuid.UUID, ctx: tuple[Caller, AsyncSession] = Depends(require(Perm.CONVERSATIONS_REPLY))) -> None:
    _caller, db = ctx
    r = (await db.execute(select(MessageRating).where(MessageRating.message_id == message_id))).scalar_one_or_none()
    if r is not None:
        await db.delete(r)
