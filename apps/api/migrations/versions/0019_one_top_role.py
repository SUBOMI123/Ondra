"""One top role: owner merges into admin (founder, 2026-11-28; docs/PLAN.md item 1).

Owners become admins, and admin gets every permission the owner had. The WhatsApp assistant (briefing, alerts)
becomes each admin's own switch (users.notification_prefs.assistant). Anything that named the owner role (who a
booking type may be booked with, routing rules that send work to "the owner") now names admin. The role list stops
allowing "owner".

Not touched, because they aren't roles: a call's `handled_by = 'owner'` (a VIP's call that rang a person directly),
and alert payloads addressed `to: 'owner'` (meaning the people at the top, now the admins).

Revision ID: 0019
Revises: 0018
"""

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The WhatsApp assistant becomes each admin's own: owners keep what the dealership had set for them; admins who
    # never got these messages start with both off (nobody is messaged on WhatsApp without their own opt-in).
    op.execute("""
        UPDATE users u SET notification_prefs = coalesce(u.notification_prefs, '{}'::jsonb) || jsonb_build_object(
            'assistant', jsonb_build_object(
                'briefing_on', coalesce((t.settings->'owner_assistant'->>'briefing_on')::boolean, false),
                'alerts_on', coalesce((t.settings->'owner_assistant'->>'alerts_on')::boolean, true)))
          FROM tenants t WHERE u.tenant_id = t.id AND u.role = 'owner'
    """)
    op.execute("""
        UPDATE users SET notification_prefs = coalesce(notification_prefs, '{}'::jsonb)
                         || '{"assistant": {"briefing_on": false, "alerts_on": false}}'::jsonb
         WHERE role = 'admin'
    """)
    # Keep a record of who was an owner: it's the dealership's history, and it lets a downgrade put exactly them back.
    op.execute("""
        INSERT INTO audit_log (tenant_id, actor_type, action, resource, before, after)
        SELECT tenant_id, 'system', 'user.role', 'user:' || id, '{"role": "owner"}', '{"role": "admin", "why": "one top role"}'
          FROM users WHERE role = 'owner'
    """)
    op.execute("UPDATE users SET role = 'admin' WHERE role = 'owner'")
    op.drop_constraint("users_role", "users", type_="check")
    op.create_check_constraint("users_role", "users", "role IN ('admin', 'manager', 'sales', 'service', 'ops', 'viewer')")
    op.execute("""
        UPDATE appointment_types
           SET eligible_roles = ARRAY(SELECT DISTINCT unnest(array_replace(eligible_roles, 'owner', 'admin')))
         WHERE 'owner' = ANY(eligible_roles)
    """)
    op.execute("""
        UPDATE routing_rules SET action = jsonb_set(action, '{assign_role}', '"admin"')
         WHERE action->>'assign_role' = 'owner'
    """)


def downgrade() -> None:
    # The people the upgrade recorded as owners become owners again. A dealership with no such record (its admins
    # were added after the upgrade) gets its oldest active admin as owner.
    op.drop_constraint("users_role", "users", type_="check")
    op.create_check_constraint("users_role", "users",
                               "role IN ('owner', 'admin', 'manager', 'sales', 'service', 'ops', 'viewer')")
    op.execute("""
        UPDATE users u SET role = 'owner'
          FROM audit_log a
         WHERE a.action = 'user.role' AND a.after->>'why' = 'one top role' AND a.resource = 'user:' || u.id AND u.role = 'admin'
    """)
    op.execute("""
        UPDATE users u SET role = 'owner'
          FROM (SELECT DISTINCT ON (tenant_id) id FROM users WHERE role = 'admin' AND active
                ORDER BY tenant_id, created_at, id) first_admin
         WHERE u.id = first_admin.id
           AND NOT EXISTS (SELECT 1 FROM users o WHERE o.tenant_id = u.tenant_id AND o.role = 'owner')
    """)
    op.execute("DELETE FROM audit_log WHERE action = 'user.role' AND after->>'why' = 'one top role'")
