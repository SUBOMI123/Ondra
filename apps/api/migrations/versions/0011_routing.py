"""Routing engine: who's on shift, whose turn it is, what a conversation is about, and named rules.

Revision ID: 0011
Revises: 0010
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A person's own working hours and timezone (null: the dealership's), so Lagos staff can cover Dallas nights.
    op.add_column("users", sa.Column("timezone", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("work_hours", postgresql.JSONB, nullable=True))
    op.add_column("users", sa.Column("max_open_tasks", sa.Integer, nullable=True))  # null: no limit
    op.add_column("users", sa.Column("last_assigned_at", sa.DateTime(timezone=True), nullable=True))  # round-robin
    op.add_column("conversations", sa.Column("topic", sa.String(20), nullable=True))
    op.add_column("routing_rules", sa.Column("name", sa.String(120), nullable=False, server_default=""))
    op.create_check_constraint("users_max_open_tasks", "users", "max_open_tasks IS NULL OR max_open_tasks > 0")


def downgrade() -> None:
    op.drop_constraint("users_max_open_tasks", "users")
    op.drop_column("routing_rules", "name")
    op.drop_column("conversations", "topic")
    for c in ("last_assigned_at", "max_open_tasks", "work_hours", "timezone"):
        op.drop_column("users", c)
