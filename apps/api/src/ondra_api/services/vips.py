"""VIPs and the person who looks after each one (docs/PLAN.md items 2 and 3).

Every VIP has a person. When that person leaves (is deactivated), their VIPs are not handed to someone else
automatically: whoever deactivates them may not know the relationship. Each VIP becomes a high-priority task for the
admins to choose someone, and until then their calls go to the VIP backup number.
"""

from __future__ import annotations

from ondra_core.models import Contact, Event, User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def orphan_vips(db: AsyncSession, gone: User) -> int:
    """`gone` was just deactivated: clear them from their VIPs and ask the admins to choose someone for each."""
    from ondra_api.services.calls import vip_backup
    from ondra_api.services.tasks import new_task

    vips = (await db.execute(select(Contact).where(Contact.is_vip.is_(True), Contact.vip_owner_user_id == gone.id,
                                                   Contact.merged_into_id.is_(None)))).scalars().all()
    if not vips:
        return 0
    admin = await vip_backup(db) or (await db.execute(select(User).where(User.role == "admin", User.active.is_(True))
                                                      .order_by(User.created_at, User.id).limit(1))).scalar_one_or_none()
    for c in vips:
        c.vip_owner_user_id = None
        first = c.display_name.split()[0]
        task = await new_task(
            db, title=f"{c.display_name}: Choose who looks after {first} (VIP)", contact_id=c.id,
            assignee_user_id=admin.id if admin else None, source="rule", urgency="high",
            brief=(f"{gone.name} no longer works here, so nobody looks after {c.display_name}. Until you choose someone, "
                   f"{first}'s calls go to the VIP backup number and their messages wait for an admin. Choose their "
                   "person on their profile (VIP settings)."))
        db.add(Event(type="vip.orphaned", payload={"contact_id": str(c.id), "was": str(gone.id), "task_id": str(task.id)}))
        db.add(Event(type="alert.created", payload={"task_id": str(task.id), "to": "owner", "urgency": "high", "contact_id": str(c.id),
                                                    "reason": f"{gone.name} left, so nobody looks after {c.display_name} (VIP). Choose someone"}))
    return len(vips)
