"""The learning loop (BUILD_PLAN.md §6.3a): what Ondra didn't know, and what people thought of what it said.

    record_gap()   the AI handed off because it didn't know: remember the question. The same question in other
                   words is the same gap (compared by embedding), so the dealer sees one line "asked 4 times".
    answer_gap()   the dealer answers once: it becomes a knowledge doc, embedded on the spot, and the AI finds it
                   on the next message that asks.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from ondra_core.models import KnowledgeDoc, KnowledgeGap, Message
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.services import knowledge

log = logging.getLogger("ondra.learning")
# How alike two questions must be to count as one. Higher than knowledge search's floor: merging two different
# questions hides one of them from the dealer, which is worse than showing a near-duplicate.
SAME_QUESTION = {"voyage-4": 0.80, "hash-v1": 0.70}
MAX_EXAMPLES = 20


def normalize(question: str) -> str:
    return " ".join(question.lower().split()).rstrip(" ?!.")[:500]


async def record_gap(db: AsyncSession, question: str, conversation_id: uuid.UUID) -> KnowledgeGap | None:
    q = normalize(question)
    if not q:
        return None
    now = datetime.now(UTC)
    # The customer's own words, kept now: by the time the dealer reads the list the conversation has moved on.
    asked = (await db.execute(select(Message.body).where(Message.conversation_id == conversation_id, Message.direction == "inbound")
                              .order_by(Message.created_at.desc()).limit(1))).scalar_one_or_none()
    asked = asked[:400] if asked else None
    gap = (await db.execute(select(KnowledgeGap).where(KnowledgeGap.question == q, KnowledgeGap.status == "open"))).scalar_one_or_none()
    vector, space = None, None
    if gap is None:
        emb = knowledge.embedder()
        try:
            [vector] = await emb.embed([q], "document")
            space = emb.space
            row = (await db.execute(text("""
                SELECT id, 1 - (embedding <=> CAST(:qv AS vector)) AS similarity FROM knowledge_gaps
                WHERE status = 'open' AND embedding IS NOT NULL AND embedding_space = :space
                ORDER BY embedding <=> CAST(:qv AS vector) LIMIT 1
            """), {"qv": knowledge._vec(vector), "space": space})).first()
            if row is not None and row.similarity >= SAME_QUESTION.get(space, 0.8):
                gap = await db.get(KnowledgeGap, row.id)
        except Exception as exc:  # noqa: BLE001  an embeddings outage must not lose the question
            log.warning("gap embedding failed (%s); matching on the exact words only", type(exc).__name__)
    if gap is not None:
        gap.occurrences += 1
        gap.last_asked_at = now
        gap.asked = asked or gap.asked
        gap.example_conversation_ids = list(dict.fromkeys([*gap.example_conversation_ids, conversation_id]))[-MAX_EXAMPLES:]
        return gap
    gap = KnowledgeGap(question=q, example_conversation_ids=[conversation_id], embedding=vector, embedding_space=space, last_asked_at=now,
                       asked=asked)
    db.add(gap)
    await db.flush()
    return gap


async def save_doc(db: AsyncSession, *, title: str, body: str, user_id: uuid.UUID, doc: KnowledgeDoc | None = None,
                   category: str | None = None) -> KnowledgeDoc:
    """Create or change an answer and embed it now, so the very next message can find it."""
    if doc is None:
        doc = KnowledgeDoc(title=title, body=body, category=category, updated_by=user_id)
        db.add(doc)
    else:
        doc.title, doc.body, doc.updated_by = title, body, user_id
        doc.embedding, doc.embedding_space = None, None  # re-embed: the words changed
    await db.flush()
    try:
        await knowledge.embed_missing(db)
    except Exception as exc:  # noqa: BLE001  full-text search still finds it; the backfill embeds it later
        log.warning("couldn't embed the answer now (%s)", type(exc).__name__)
    await db.refresh(doc)
    return doc


async def answer_gap(db: AsyncSession, gap: KnowledgeGap, *, title: str, answer: str, user_id: uuid.UUID) -> KnowledgeDoc:
    doc = await save_doc(db, title=title, body=answer, user_id=user_id, category="answered question")
    gap.status, gap.answer_doc_id = "answered", doc.id
    return doc
