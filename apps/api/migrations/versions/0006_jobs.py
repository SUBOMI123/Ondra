"""Step 3: a durable job queue in Postgres, and the lookups workers need before a tenant is known.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

APP_ROLE = "ondra_app"


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("payload", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("status", sa.String(10), server_default="queued", nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="5", nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text("NULLIF(current_setting('app.tenant_id', true), '')::uuid")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("status IN ('queued', 'running', 'done', 'failed')", name="jobs_status"),
    )
    op.create_index("ix_jobs_tenant_id", "jobs", ["tenant_id"])
    op.create_index("jobs_ready", "jobs", ["status", "run_at"])
    op.execute("ALTER TABLE jobs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE jobs FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON jobs USING (tenant_id = app_current_tenant()) "
               "WITH CHECK (tenant_id = app_current_tenant())")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON jobs TO {APP_ROLE}")

    # Workers claim ready jobs across tenants. A job stuck in 'running' past its lease (a crashed worker) is
    # claimable again. Returns only what's needed to open the right tenant's session.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION jobs_claim(p_limit int, p_lease_seconds int)
        RETURNS TABLE (id uuid, tenant_id uuid, kind text, payload jsonb, attempts int, max_attempts int)
        LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = public AS $$
          UPDATE jobs j SET status = 'running', locked_at = now(), attempts = j.attempts + 1, updated_at = now()
          WHERE j.id IN (
            SELECT id FROM jobs
            WHERE (status = 'queued' AND run_at <= now())
               OR (status = 'running' AND locked_at < now() - make_interval(secs => p_lease_seconds))
            ORDER BY run_at
            FOR UPDATE SKIP LOCKED
            LIMIT p_limit
          )
          RETURNING j.id, j.tenant_id, j.kind::text, j.payload, j.attempts, j.max_attempts
        $$
        """
    )
    # Which dealers have overdue, not-yet-escalated tasks. Tenant ids only.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION tenants_with_overdue_tasks() RETURNS SETOF uuid
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
          SELECT DISTINCT tenant_id FROM tasks
          WHERE status IN ('open', 'in_progress') AND due_at < now() AND escalated_at IS NULL
        $$
        """
    )
    for fn in ("jobs_claim(int, int)", "tenants_with_overdue_tasks()"):
        op.execute(f"REVOKE ALL ON FUNCTION {fn} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {fn} TO {APP_ROLE}")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS tenants_with_overdue_tasks()")
    op.execute("DROP FUNCTION IF EXISTS jobs_claim(int, int)")
    op.drop_table("jobs")
