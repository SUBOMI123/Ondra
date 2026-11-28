"""Live updates: a change in one dealer's data reaches that dealer's subscribers, with ids only, and nobody else's."""

import asyncio

from sqlalchemy import select

from ondra_api.db import tenant_session
from ondra_api.live import broker
from ondra_api.services.tasks import new_task
from ondra_core.models import User

from .conftest import login


async def _next(q, timeout=3.0):
    return await asyncio.wait_for(q.get(), timeout)


async def test_changes_reach_only_the_right_dealer_with_ids_only(database):
    qa = await broker.subscribe(database["a"])
    qb = await broker.subscribe(database["b"])
    try:
        async with tenant_session(database["a"]) as db:
            owner = (await db.execute(select(User.id).where(User.email == "owner@prestigemotors.example"))).scalar_one()
            t = await new_task(db, title="Live check", assignee_user_id=owner)
            task_id = str(t.id)
        got = await _next(qa)
        while got["id"] != task_id:
            got = await _next(qa)
        assert got["table"] == "tasks" and set(got) == {"tenant_id", "table", "id", "conversation_id"}
        await asyncio.sleep(0.3)
        assert qb.empty()  # the other dealer heard nothing
    finally:
        broker.unsubscribe(database["a"], qa)
        broker.unsubscribe(database["b"], qb)


async def test_stream_needs_a_signed_in_user(client, database):
    assert (await client.get("/live")).status_code == 401
    assert (await client.get("/live", headers={"Authorization": "Bearer nonsense"})).status_code == 401
    await login(client, "owner@prestigemotors.example")  # a valid token streams (checked live; ASGI test client buffers)
