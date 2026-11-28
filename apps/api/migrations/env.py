"""Alembic runs as the owner role (MIGRATIONS_DATABASE_URL). The API itself never connects as the owner."""

import asyncio
import os

from alembic import context
from ondra_core.models import Base
from sqlalchemy.ext.asyncio import create_async_engine

target_metadata = Base.metadata


def _url() -> str:
    url = os.environ.get("MIGRATIONS_DATABASE_URL")
    if not url:
        raise RuntimeError("Set MIGRATIONS_DATABASE_URL (see .env.example)")
    return url


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def _main() -> None:
    engine = create_async_engine(_url())
    async with engine.connect() as conn:
        await conn.run_sync(_run)
    await engine.dispose()


asyncio.run(_main())
