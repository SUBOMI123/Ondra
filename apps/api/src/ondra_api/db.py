"""Database access. Every request that touches dealer data runs inside `tenant_session`, which sets the tenant
for the transaction so Postgres row-level security filters every read and checks every write."""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from ondra_api.config import get_settings

_engine: AsyncEngine | None = None
_sessions: async_sessionmaker[AsyncSession] | None = None


def engine() -> AsyncEngine:
    global _engine, _sessions
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
        _sessions = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def sessionmaker() -> async_sessionmaker[AsyncSession]:
    engine()
    assert _sessions is not None
    return _sessions


@asynccontextmanager
async def tenant_session(tenant_id: uuid.UUID) -> AsyncIterator[AsyncSession]:
    """A session whose transaction can only see and write `tenant_id`'s rows. Commits on success."""
    async with sessionmaker()() as session:
        async with session.begin():
            # set_config(..., true) is transaction-local, so the setting can't leak to the next pooled use.
            await session.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)})
            yield session


@asynccontextmanager
async def no_tenant_session() -> AsyncIterator[AsyncSession]:
    """For the few calls made before a tenant is known (sign-in). RLS hides every dealer row here."""
    async with sessionmaker()() as session:
        async with session.begin():
            yield session
