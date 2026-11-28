"""Tests run against a real Postgres (the same image as docker compose) in a fresh `ondra_test` database. The set-up
is shared with the other suites: see `ondra_api.testing`."""

import uuid

import pytest
from ondra_api.testing import configure_env, ensure_test_database

configure_env()

import httpx
from ondra_api.main import app
from ondra_api.seed import DEV_PASSWORD


@pytest.fixture(scope="session")
async def database():
    return await ensure_test_database()


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
