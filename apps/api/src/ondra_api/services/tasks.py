"""Task deadlines and escalation (BUILD_PLAN.md §7: SLA timers per task; breach escalates to a manager or owner)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ondra_api.services.agent_tools import assignee_for
from ondra_api.services.sla import due_for
from ondra_core.models import Event, Task, Tenant, User


async def new_task(db: AsyncSession, **fields) -> Task:
    """Create a task with a due time from its urgency, counted in the dealer's opening hours."""
    tenant = (await db.execute(select(Tenant).limit(1))).scalar_one()
    urgency = fields.get("urgency") or "normal"
    due_at = fields.pop("due_at", None) or due_for(tenant, urgency)
    task = Task(**fields, due_at=due_at)
    db.add(task)
    await db.flush()
    return task


async def escalate_overdue(db: AsyncSession, now: datetime | None = None) -> list[Task]:
    """Every open task past its due time is escalated once: marked high urgency and handed up, to a manager if a
    manager wasn't already on it, otherwise to the owner. The person it was with is recorded in the event."""
    now = now or datetime.now(UTC)
    overdue = (await db.execute(
        select(Task).where(Task.status.in_(("open", "in_progress")), Task.due_at < now, Task.escalated_at.is_(None))
    )).scalars().all()
    for t in overdue:
        current = await db.get(User, t.assignee_user_id) if t.assignee_user_id else None
        target_role = "owner" if current is not None and current.role in ("manager", "owner") else "manager"
        new_assignee = await assignee_for(db, target_role)
        db.add(Event(type="task.escalated", payload={
            "task_id": str(t.id), "from_user_id": str(t.assignee_user_id) if t.assignee_user_id else None,
            "to_user_id": str(new_assignee) if new_assignee else None, "was_due": t.due_at.isoformat(),
        }))
        db.add(Event(type="alert.created", payload={"task_id": str(t.id), "to": target_role, "urgency": "high",
                                                     "reason": "Task overdue"}))
        t.escalated_at = now
        t.urgency = "high"
        if new_assignee:
            t.assignee_user_id = new_assignee
    await db.flush()
    return list(overdue)
