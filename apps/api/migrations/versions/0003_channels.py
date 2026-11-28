"""Step 2: dealer channel addresses, task urgency, and the tenant lookup for inbound webhooks.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

APP_ROLE = "ondra_app"


def enable_tenant_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {table} "
        f"USING (tenant_id = app_current_tenant()) WITH CHECK (tenant_id = app_current_tenant())"
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {APP_ROLE}")


def upgrade() -> None:
    op.create_table(
        "channel_addresses",
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("address", sa.String(320), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text("NULLIF(current_setting('app.tenant_id', true), '')::uuid")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel", "address", name="channel_addresses_unique"),
    )
    op.create_index("ix_channel_addresses_tenant_id", "channel_addresses", ["tenant_id"])
    enable_tenant_rls("channel_addresses")

    op.add_column("tasks", sa.Column("urgency", sa.String(10), server_default="normal", nullable=False))
    op.create_check_constraint("tasks_urgency", "tasks", "urgency IN ('low', 'normal', 'high')")

    # Inbound webhooks arrive before a tenant is known. This returns only the tenant id for an active address.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION channel_find_tenant(p_channel text, p_address text) RETURNS uuid
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
          SELECT tenant_id FROM channel_addresses WHERE channel = p_channel AND address = p_address AND active
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION channel_find_tenant(text, text) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION channel_find_tenant(text, text) TO {APP_ROLE}")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS channel_find_tenant(text, text)")
    op.drop_constraint("tasks_urgency", "tasks")
    op.drop_column("tasks", "urgency")
    op.drop_table("channel_addresses")
