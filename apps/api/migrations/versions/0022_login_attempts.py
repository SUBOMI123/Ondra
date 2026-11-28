"""Failed sign-in attempts, so password guessing is throttled (security audit, 2026-11-28).

Only failures are kept, for a day. Not dealer data: a sign-in happens before a dealership is known, so the table
has no tenant_id and no row-level security; the app role can only add, count and prune rows.

Revision ID: 0022
Revises: 0021
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

APP_ROLE = "ondra_app"


def upgrade() -> None:
    op.create_table(
        "login_attempts",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("email", postgresql.CITEXT, nullable=False),
        sa.Column("ip", sa.String(64)),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("login_attempts_email_at", "login_attempts", ["email", "at"])
    op.create_index("login_attempts_ip_at", "login_attempts", ["ip", "at"])
    op.execute(f"GRANT SELECT, INSERT, DELETE ON login_attempts TO {APP_ROLE}")


def downgrade() -> None:
    op.drop_table("login_attempts")
