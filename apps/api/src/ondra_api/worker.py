"""The worker: runs queued jobs and the escalation sweep.

    python -m ondra_api.worker            # forever (docker compose service `worker`)

Jobs are claimed across tenants by `jobs_claim` (SKIP LOCKED, so several workers can run side by side); each job then
runs inside its own tenant's session, under row-level security like any API request. A failed job is retried with
backoff (10 s, 20 s, 40 s...) up to max_attempts, then marked failed with its error kept for inspection.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

from ondra_core.models import Job
from sqlalchemy import text

from ondra_api.db import no_tenant_session, tenant_session
from ondra_api.services import inbound
from ondra_api.services.tasks import escalate_overdue

log = logging.getLogger("ondra.worker")
LEASE_SECONDS = 120
POLL_SECONDS = 1.0
SWEEP_SECONDS = 60


async def _agent_turn(tenant_id: uuid.UUID, p: dict) -> None:
    await inbound.run_agent(tenant_id, uuid.UUID(p["conversation_id"]), uuid.UUID(p["message_id"]), p["draft"])


async def _reminder(tenant_id: uuid.UUID, p: dict) -> None:
    from ondra_api.services.reminders import send_reminder

    log.info("reminder %s: %s", p.get("appointment_id"), await send_reminder(tenant_id, p))


HANDLERS = {"agent_turn": _agent_turn, "appointment_reminder": _reminder}


async def run_once(limit: int = 10) -> int:
    """Claim and run up to `limit` ready jobs. Returns how many ran."""
    async with no_tenant_session() as db:
        claimed = (await db.execute(text("SELECT * FROM jobs_claim(:n, :lease)"),
                                    {"n": limit, "lease": LEASE_SECONDS})).mappings().all()
    for j in claimed:
        error = None
        try:
            await HANDLERS[j["kind"]](j["tenant_id"], j["payload"])
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"[:2000]
            log.exception("job %s (%s) failed", j["id"], j["kind"])
        async with tenant_session(j["tenant_id"]) as db:
            job = await db.get(Job, j["id"])
            if error is None:
                job.status, job.last_error = "done", None
            elif j["attempts"] >= j["max_attempts"]:
                job.status, job.last_error = "failed", error
            else:
                job.status, job.last_error = "queued", error
                job.run_at = datetime.now(UTC) + timedelta(seconds=10 * 2 ** (j["attempts"] - 1))
    return len(claimed)


async def sweep() -> int:
    """Escalate overdue tasks in every dealership that has any."""
    async with no_tenant_session() as db:
        tenants = (await db.execute(text("SELECT * FROM tenants_with_overdue_tasks()"))).scalars().all()
    n = 0
    for t in tenants:
        async with tenant_session(t) as db:
            n += len(await escalate_overdue(db))
    return n


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    log.info("worker started")
    last_sweep = 0.0
    loop = asyncio.get_running_loop()
    while True:
        try:
            ran = await run_once()
            if loop.time() - last_sweep >= SWEEP_SECONDS:
                if (n := await sweep()):
                    log.info("escalated %d overdue tasks", n)
                last_sweep = loop.time()
        except Exception:
            log.exception("worker loop error")
            ran = 0
        if not ran:
            await asyncio.sleep(POLL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
