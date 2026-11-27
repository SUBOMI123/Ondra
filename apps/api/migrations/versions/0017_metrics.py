"""Daily rollups of the dashboard's numbers, computed from events.

Revision ID: 0017
Revises: 0016
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

APP_ROLE = "ondra_app"


def upgrade() -> None:
    op.create_table(
        "metric_days",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False,
                  server_default=sa.text("NULLIF(current_setting('app.tenant_id', true), '')::uuid"), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("day", sa.Date, nullable=False),  # the dealership's own calendar day
        sa.Column("data", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("events", sa.Integer, nullable=False, server_default="0"),  # how many events it was computed from
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "day", name="metric_days_day"),
    )
    op.execute("ALTER TABLE metric_days ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE metric_days FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON metric_days USING (tenant_id = app_current_tenant()) "
               "WITH CHECK (tenant_id = app_current_tenant())")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON metric_days TO {APP_ROLE}")


def downgrade() -> None:
    op.drop_table("metric_days")
