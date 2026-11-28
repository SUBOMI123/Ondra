"""The owner's WhatsApp assistant: its thread, and alerts queued for delivery as they're raised.

Revision ID: 0016
Revises: 0015
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

APP_ROLE = "ondra_app"


def upgrade() -> None:
    op.create_table(
        "assistant_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False,
                  server_default=sa.text("NULLIF(current_setting('app.tenant_id', true), '')::uuid"), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("direction", sa.String(3), nullable=False),  # in: from the owner; out: to the owner
        sa.Column("kind", sa.String(12), nullable=False, server_default="text"),
        sa.Column("body", sa.Text, nullable=False, server_default=""),
        sa.Column("meta", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("provider_message_id", sa.String(200), nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="ok"),
        sa.CheckConstraint("direction IN ('in', 'out')", name="assistant_messages_direction"),
        sa.CheckConstraint("kind IN ('text', 'voice', 'button', 'briefing', 'alert', 'reply')", name="assistant_messages_kind"),
        sa.UniqueConstraint("tenant_id", "provider_message_id", name="assistant_messages_provider_id"),
    )
    op.execute("ALTER TABLE assistant_messages ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE assistant_messages FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON assistant_messages USING (tenant_id = app_current_tenant()) "
               "WITH CHECK (tenant_id = app_current_tenant())")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON assistant_messages TO {APP_ROLE}")
    # Every alert raised for the owner is queued for delivery in the same transaction that raised it, wherever in
    # the code that was (VIP messages and calls, overdue tasks reaching the owner, re-alerts).
    op.execute("""
        CREATE OR REPLACE FUNCTION queue_owner_alert() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.type = 'alert.created' AND NEW.payload->>'to' = 'owner' THEN
            INSERT INTO jobs (tenant_id, kind, payload) VALUES (NEW.tenant_id, 'owner_alert', NEW.payload || jsonb_build_object('event_id', NEW.id));
          END IF;
          RETURN NEW;
        END $$
    """)
    op.execute("CREATE TRIGGER events_owner_alert AFTER INSERT ON events FOR EACH ROW EXECUTE FUNCTION queue_owner_alert()")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS events_owner_alert ON events")
    op.execute("DROP FUNCTION IF EXISTS queue_owner_alert()")
    op.drop_table("assistant_messages")
