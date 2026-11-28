"""Step 5: calls carry the caller, who handled them, timings and call-back state; a phone channel per dealer.

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("calls", sa.Column("contact_id", postgresql.UUID(as_uuid=True),
                                     sa.ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_calls_contact_id", "calls", ["contact_id"])
    op.add_column("calls", sa.Column("from_number", sa.String(32), nullable=True))
    op.add_column("calls", sa.Column("to_number", sa.String(32), nullable=True))
    op.add_column("calls", sa.Column("handled_by", sa.String(10), nullable=True))
    op.add_column("calls", sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("calls", sa.Column("transferred_to_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("calls", sa.Column("metrics", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("calls", sa.Column("callback_done_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint("calls_handled_by", "calls", "handled_by IS NULL OR handled_by IN ('ai', 'staff', 'owner', 'missed')")
    op.create_unique_constraint("calls_provider_call_sid", "calls", ["tenant_id", "provider_call_sid"])
    op.execute("CREATE TRIGGER calls_notify AFTER INSERT OR UPDATE ON calls FOR EACH ROW EXECUTE FUNCTION notify_change()")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION notify_change() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
          conv uuid;
        BEGIN
          IF TG_TABLE_NAME IN ('messages', 'tasks', 'appointments', 'calls') THEN conv := NEW.conversation_id;
          ELSIF TG_TABLE_NAME = 'conversations' THEN conv := NEW.id;
          END IF;
          PERFORM pg_notify('ondra_changes', json_build_object(
            'tenant_id', NEW.tenant_id, 'table', TG_TABLE_NAME, 'id', NEW.id, 'conversation_id', conv
          )::text);
          RETURN NEW;
        END $$
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS calls_notify ON calls")
    op.drop_constraint("calls_provider_call_sid", "calls")
    op.drop_constraint("calls_handled_by", "calls")
    for col in ("callback_done_at", "metrics", "transferred_to_user_id", "ended_at", "handled_by", "to_number",
                "from_number", "contact_id"):
        op.drop_column("calls", col)
