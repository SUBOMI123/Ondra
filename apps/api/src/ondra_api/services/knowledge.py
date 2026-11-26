"""Knowledge search: semantic (embeddings) first, Postgres full-text as the fallback.

Every query runs in the caller's tenant session, so row-level security limits it to the current dealer's answers.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from ondra_core.embeddings import MIN_SIMILARITY, Embedder, make_embedder
from ondra_core.models import KnowledgeDoc
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.config import get_settings

log = logging.getLogger("ondra.knowledge")


@lru_cache
def embedder() -> Embedder:
    return make_embedder(get_settings().voyage_api_key or None)


def _vec(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in v) + "]"


async def embed_missing(db: AsyncSession, emb: Embedder | None = None) -> int:
    """Embed every answer that has no vector in the current embedder's space. Returns how many were embedded."""
    emb = emb or embedder()
    docs = (await db.execute(select(KnowledgeDoc).where(
        (KnowledgeDoc.embedding.is_(None)) | (KnowledgeDoc.embedding_space != emb.space)
    ))).scalars().all()
    if not docs:
        return 0
    vectors = await emb.embed([f"{d.title}\n{d.body}" for d in docs], "document")
    for d, v in zip(docs, vectors, strict=True):
        d.embedding, d.embedding_space = v, emb.space
    await db.flush()
    return len(docs)


async def _full_text(db: AsyncSession, query: str) -> list[dict]:
    rows = (await db.execute(text("""
        SELECT title, body FROM knowledge_docs,
             to_tsvector('english', title || ' ' || body) AS doc,
             CAST(NULLIF(replace(plainto_tsquery('english', :q)::text, '&', '|'), '') AS tsquery) AS q
        WHERE doc @@ q ORDER BY ts_rank(doc, q) DESC LIMIT 3
    """), {"q": query})).all()
    return [{"title": r.title, "answer": r.body} for r in rows]


async def search(db: AsyncSession, query: str, emb: Embedder | None = None) -> list[dict]:
    emb = emb or embedder()
    try:
        [qv] = await emb.embed([query], "query")
    except Exception as exc:  # noqa: BLE001  an embeddings outage must not stop the AI answering
        log.warning("embedding failed (%s); using full-text search", type(exc).__name__)
        return await _full_text(db, query)
    rows = (await db.execute(text("""
        SELECT title, body, 1 - (embedding <=> CAST(:qv AS vector)) AS similarity FROM knowledge_docs
        WHERE embedding IS NOT NULL AND embedding_space = :space
        ORDER BY embedding <=> CAST(:qv AS vector) LIMIT 3
    """), {"qv": _vec(qv), "space": emb.space})).all()
    if not rows:  # nothing embedded in this space yet
        return await _full_text(db, query)
    floor = MIN_SIMILARITY.get(emb.space, 0.4)
    return [{"title": r.title, "answer": r.body} for r in rows if r.similarity >= floor]


if __name__ == "__main__":
    # Backfill: uv run python -m ondra_api.services.knowledge  (embeds every dealer's unembedded answers)
    import asyncio

    from ondra_api.db import tenant_session

    async def main() -> None:
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        owner = create_async_engine(get_settings().migrations_database_url)
        async with async_sessionmaker(owner)() as db:
            tenants = (await db.execute(text("SELECT id FROM tenants"))).scalars().all()
        await owner.dispose()
        for t in tenants:
            async with tenant_session(t) as db:
                print(t, await embed_missing(db))

    asyncio.run(main())
