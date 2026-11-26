"""Step 4: booking without double-booking.

Appointments block their person from starts_at to blocks_until (end + buffer). An exclusion constraint refuses any
overlap for the same person among live appointments, and appointment_resources does the same per bay or loaner.
The database enforces it, so two bookings racing for the same slot can't both succeed.

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

APP_ROLE = "ondra_app"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")  # equality on uuid inside a GiST exclusion constraint

    op.add_column("appointment_types", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("appointments", sa.Column("blocks_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("appointments", sa.Column("conversation_id", postgresql.UUID(as_uuid=True),
                                            sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True))
    op.add_column("appointments", sa.Column("details", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("appointments", sa.Column("reminders_sent", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.execute("UPDATE appointments SET blocks_until = ends_at WHERE blocks_until IS NULL")
    op.execute(
        "ALTER TABLE appointments ADD CONSTRAINT appointments_no_double_booking EXCLUDE USING gist "
        "(tenant_id WITH =, assigned_user_id WITH =, tstzrange(starts_at, blocks_until) WITH &&) "
        "WHERE (status IN ('booked', 'confirmed') AND assigned_user_id IS NOT NULL)"
    )

    op.create_table(
        "appointment_resources",
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocks_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text("NULLIF(current_setting('app.tenant_id', true), '')::uuid")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_appointment_resources_tenant_id", "appointment_resources", ["tenant_id"])
    op.create_index("ix_appointment_resources_appointment_id", "appointment_resources", ["appointment_id"])
    op.execute(
        "ALTER TABLE appointment_resources ADD CONSTRAINT resources_no_double_booking EXCLUDE USING gist "
        "(tenant_id WITH =, resource_id WITH =, tstzrange(starts_at, blocks_until) WITH &&) WHERE (active)"
    )
    op.execute("ALTER TABLE appointment_resources ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE appointment_resources FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON appointment_resources USING (tenant_id = app_current_tenant()) "
               "WITH CHECK (tenant_id = app_current_tenant())")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON appointment_resources TO {APP_ROLE}")
    # Live updates for the calendar.
    op.execute("CREATE TRIGGER appointments_notify AFTER INSERT OR UPDATE ON appointments FOR EACH ROW EXECUTE FUNCTION notify_change()")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION notify_change() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
          conv uuid;
        BEGIN
          IF TG_TABLE_NAME IN ('messages', 'tasks', 'appointments') THEN conv := NEW.conversation_id;
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
    op.execute("DROP TRIGGER IF EXISTS appointments_notify ON appointments")
    op.drop_table("appointment_resources")
    op.execute("ALTER TABLE appointments DROP CONSTRAINT IF EXISTS appointments_no_double_booking")
    for col in ("reminders_sent", "details", "conversation_id", "blocks_until"):
        op.drop_column("appointments", col)
    op.drop_column("appointment_types", "description")
