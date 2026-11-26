"""Test support shared by every Python test suite (apps/api, apps/voice): a fresh `ondra_test` database with the
migrations run from scratch, the example dealership from the seed, and a second dealership for isolation tests.
Created once per test run, however many suites ask for it. Never used outside tests."""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

ADMIN_URL = os.environ.get("TEST_ADMIN_DATABASE_URL", "postgresql://ondra_owner:ondra_owner_dev@localhost:5432/postgres")
OWNER_URL = "postgresql+asyncpg://ondra_owner:ondra_owner_dev@localhost:5432/ondra_test"
APP_URL = "postgresql+asyncpg://ondra_app:ondra_app_dev@localhost:5432/ondra_test"
API_DIR = Path(__file__).resolve().parents[2]

_created: dict | None = None


def configure_env() -> None:
    """Call before importing the app. Tests never call real providers: blank the keys a developer's .env may hold
    (env vars win over .env)."""
    os.environ.update(DATABASE_URL=APP_URL, MIGRATIONS_DATABASE_URL=OWNER_URL, JWT_SECRET="test-secret-" + "x" * 32,
                      ANTHROPIC_API_KEY="", VOYAGE_API_KEY="")


async def ensure_test_database() -> dict:
    global _created
    if _created is not None:
        return _created
    import asyncpg
    from ondra_core.models import Contact, Tenant, User, Vehicle
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from ondra_api.security import hash_password
    from ondra_api.seed import DEV_PASSWORD, seed

    conn = await asyncpg.connect(ADMIN_URL)
    await conn.execute("DROP DATABASE IF EXISTS ondra_test WITH (FORCE)")
    await conn.execute("CREATE DATABASE ondra_test")
    await conn.execute("GRANT CONNECT ON DATABASE ondra_test TO ondra_app")
    await conn.close()
    await asyncio.to_thread(subprocess.run, ["alembic", "upgrade", "head"], cwd=API_DIR, check=True,
                            env=os.environ | {"MIGRATIONS_DATABASE_URL": OWNER_URL})
    tenant_a = await seed()

    # A second dealership, created as the owner role, with one user, contact and vehicle.
    engine = create_async_engine(OWNER_URL)
    async with async_sessionmaker(engine, expire_on_commit=False)() as db, db.begin():
        b = Tenant(name="Lone Star Autos")
        db.add(b)
        await db.flush()
        db.add(User(tenant_id=b.id, email="owner@lonestar.example", name="Lone Star Owner", role="owner",
                    password_hash=hash_password(DEV_PASSWORD)))
        db.add(Contact(tenant_id=b.id, display_name="Only In Tenant B"))
        db.add(Vehicle(tenant_id=b.id, stock_number="B-1", year=2024, make="Kia", model="Telluride"))
        tenant_b = b.id
    await engine.dispose()
    _created = {"a": tenant_a, "b": tenant_b}
    return _created
