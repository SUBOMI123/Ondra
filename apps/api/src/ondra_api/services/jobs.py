"""Enqueue durable jobs. Call inside a tenant session: the job is written in the same transaction as the work that
needs it (a message and the AI turn that answers it are saved together, or not at all)."""

from __future__ import annotations

from datetime import datetime

from ondra_core.models import Job
from sqlalchemy.ext.asyncio import AsyncSession


def enqueue(db: AsyncSession, kind: str, payload: dict, run_at: datetime | None = None) -> Job:
    job = Job(kind=kind, payload=payload, **({"run_at": run_at} if run_at else {}))
    db.add(job)
    return job
