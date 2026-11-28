"""Booking confirmations (docs/PLAN.md item 4).

- messages.meta: per-message send options the plain body can't carry (an email's subject; attachments ride in the
  existing `attachments` column).
- appointments.confirmations: what was sent for each booking, move and cancellation, and why anything wasn't
  ("No confirmation text: no consent on file"), so staff can see it on the appointment.

Revision ID: 0020
Revises: 0019
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("meta", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("appointments", sa.Column("confirmations", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")))


def downgrade() -> None:
    op.drop_column("appointments", "confirmations")
    op.drop_column("messages", "meta")
