"""Tests run against a real Postgres (the same image as docker compose) in a fresh `ondra_test` database:
migrations from scratch, the example dealership from the seed, and a second dealership for isolation tests."""

import os
import subprocess
import uuid
from pathlib import Path

import pytest

ADMIN_URL = os.environ.get("TEST_ADMIN_DATABASE_URL", "postgresql://ondra_owner:ondra_owner_dev@localhost:5432/postgres")
OWNER_URL = "postgresql+asyncpg://ondra_owner:ondra_owner_dev@localhost:5432/ondra_test"
APP_URL = "postgresql+asyncpg://ondra_app:ondra_app_dev@localhost:5432/ondra_test"
# Tests never call real providers: blank the keys a developer's .env may hold (env vars win over .env).
os.environ.update(DATABASE_URL=APP_URL, MIGRATIONS_DATABASE_URL=OWNER_URL, JWT_SECRET="test-secret-" + "x" * 32,
                  ANTHROPIC_API_KEY="", VOYAGE_API_KEY="")

import asyncpg
import httpx
from ondra_api.main import app
from ondra_api.security import hash_password
from ondra_api.seed import DEV_PASSWORD, seed
from ondra_core.models import Contact, Tenant, User, Vehicle
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

API_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
async def database():
    conn = await asyncpg.connect(ADMIN_URL)
    await conn.execute("DROP DATABASE IF EXISTS ondra_test WITH (FORCE)")
    await conn.execute("CREATE DATABASE ondra_test")
    await conn.execute("GRANT CONNECT ON DATABASE ondra_test TO ondra_app")
    await conn.close()
    subprocess.run(["alembic", "upgrade", "head"], cwd=API_DIR, check=True, env=os.environ | {"MIGRATIONS_DATABASE_URL": OWNER_URL})
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
    return {"a": tenant_a, "b": tenant_b}


@pytest.fixture
async def client(database):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def login(client: httpx.AsyncClient, email: str, password: str = DEV_PASSWORD) -> dict:
    r = await client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def new_id() -> uuid.UUID:
    return uuid.uuid4()
