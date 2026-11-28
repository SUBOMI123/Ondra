"""When a lead was pushed to the dealer's CRM (once per deal).

Revision ID: 0015
Revises: 0014
"""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("deals", sa.Column("crm_pushed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("deals", "crm_pushed_at")
