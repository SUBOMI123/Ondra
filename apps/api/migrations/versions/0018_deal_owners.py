"""Give older deals a salesperson: whoever has the client's conversation, else whoever has an open task about them.

Deals Ondra opens get one when they open (since 2026-11-27); this catches the ones from before, so "Mine" on the
Deals board is complete. VIP deals are left alone: the VIP's handler has them. Deals with neither stay unassigned,
for a manager to hand to someone.

Revision ID: 0018
Revises: 0017
"""

from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE deals d SET owner_user_id = pick.user_id
        FROM (
          SELECT DISTINCT ON (d2.id) d2.id AS deal_id, x.user_id
          FROM deals d2
          JOIN contacts c ON c.id = d2.contact_id AND c.tenant_id = d2.tenant_id AND NOT c.is_vip
          JOIN LATERAL (
            SELECT cv.assigned_user_id AS user_id, 0 AS pref, cv.updated_at AS at
              FROM conversations cv WHERE cv.contact_id = c.id AND cv.tenant_id = d2.tenant_id AND cv.assigned_user_id IS NOT NULL
            UNION ALL
            SELECT t.assignee_user_id, 1, t.created_at
              FROM tasks t WHERE t.contact_id = c.id AND t.tenant_id = d2.tenant_id AND t.assignee_user_id IS NOT NULL
               AND t.status IN ('open', 'in_progress')
          ) x ON true
          JOIN users u ON u.id = x.user_id AND u.tenant_id = d2.tenant_id AND u.active
          WHERE d2.owner_user_id IS NULL
          ORDER BY d2.id, x.pref, x.at DESC
        ) pick
        WHERE d.id = pick.deal_id
    """)


def downgrade() -> None:
    pass  # which deals were filled in isn't recorded; leaving owners in place is harmless
