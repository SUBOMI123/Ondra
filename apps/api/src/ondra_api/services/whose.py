"""Whose work a screen shows: the person's own ("mine") or the whole dealership's ("everyone").

Every list screen (Inbox, Calls, Calendar, Tasks, Deals) takes the same switch. What "mine" means follows the thing
listed: a task is yours when it's assigned to you, a deal when you own it, an appointment when it's with you. A
conversation or a call is yours when the client is: you've been given their conversation, you own their deal, you
look after them as a VIP, or you have an open task for them. VIP visibility is applied separately and always.
"""

import uuid
from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

Whose = Literal["mine", "everyone"]


async def my_clients(db: AsyncSession, me: uuid.UUID) -> set[uuid.UUID]:
    rows = await db.execute(text("""
        SELECT contact_id FROM conversations WHERE assigned_user_id = :me
        UNION SELECT contact_id FROM deals WHERE owner_user_id = :me
        UNION SELECT id FROM contacts WHERE vip_owner_user_id = :me
        UNION SELECT contact_id FROM tasks WHERE assignee_user_id = :me AND status IN ('open', 'in_progress')
                                             AND contact_id IS NOT NULL
    """), {"me": me})
    return {r[0] for r in rows}
