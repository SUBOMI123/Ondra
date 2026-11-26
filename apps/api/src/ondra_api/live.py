"""Live updates to the dashboard (Step 3: "Inbox UI with realtime").

Postgres triggers NOTIFY `ondra_changes` with ids only. One listener connection per API process receives every
notice and hands each to the open streams of that notice's dealer only. The stream endpoint checks the caller once,
then holds no database transaction while it's open (streams live for hours).

    GET /live   text/event-stream; send the access token as a Bearer header (the dashboard reads it with fetch)
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator

import asyncpg
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from ondra_api.config import get_settings

log = logging.getLogger("ondra.live")
router = APIRouter(tags=["live"])
HEARTBEAT_SECONDS = 15
QUEUE_SIZE = 200


class Broker:
    def __init__(self) -> None:
        self._subs: dict[uuid.UUID, set[asyncio.Queue]] = defaultdict(set)
        self._conn: asyncpg.Connection | None = None
        self._lock = asyncio.Lock()

    async def _ensure_listening(self) -> None:
        async with self._lock:
            if self._conn is not None and not self._conn.is_closed():
                return
            dsn = get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://")
            self._conn = await asyncpg.connect(dsn)
            await self._conn.add_listener("ondra_changes", self._on_notify)

    def _on_notify(self, _conn, _pid, _channel, payload: str) -> None:
        try:
            data = json.loads(payload)
            tenant = uuid.UUID(data["tenant_id"])
        except (ValueError, KeyError, TypeError):
            return
        for q in list(self._subs.get(tenant, ())):
            with contextlib.suppress(asyncio.QueueFull):  # a stalled client drops notices, never blocks others
                q.put_nowait(data)

    async def subscribe(self, tenant_id: uuid.UUID) -> asyncio.Queue:
        await self._ensure_listening()
        q: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_SIZE)
        self._subs[tenant_id].add(q)
        return q

    def unsubscribe(self, tenant_id: uuid.UUID, q: asyncio.Queue) -> None:
        self._subs[tenant_id].discard(q)
        if not self._subs[tenant_id]:
            del self._subs[tenant_id]


broker = Broker()


async def _caller_tenant(request: Request) -> uuid.UUID:
    from ondra_api.deps import MFA_REQUIRED, authenticate

    caller, session = await authenticate(request)  # short check, then no transaction while streaming
    await session.info.pop("cm").__aexit__(None, None, None)
    if caller.mfa_missing:
        raise HTTPException(403, MFA_REQUIRED)
    return caller.tenant_id


@router.get("/live")
async def live(request: Request) -> StreamingResponse:
    tenant_id = await _caller_tenant(request)
    q = await broker.subscribe(tenant_id)

    async def stream() -> AsyncIterator[str]:
        try:
            yield ": connected\n\n"
            while not await request.is_disconnected():
                try:
                    data = await asyncio.wait_for(q.get(), timeout=HEARTBEAT_SECONDS)
                    yield f"event: change\ndata: {json.dumps(data)}\n\n"
                except TimeoutError:
                    yield ": heartbeat\n\n"  # keeps proxies from closing an idle stream
        finally:
            broker.unsubscribe(tenant_id, q)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
