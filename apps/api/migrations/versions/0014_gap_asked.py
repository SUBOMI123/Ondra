"""An unanswered question keeps a customer's own words, saved when it was asked.

Revision ID: 0014
Revises: 0013
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_gaps", sa.Column("asked", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("knowledge_gaps", "asked")
