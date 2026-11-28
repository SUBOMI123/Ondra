"""Team invites: a one-time token (stored only as a hash) that lets a new teammate set their password.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("invite_token_hash", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("invite_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("users_invite_token_hash", "users", ["invite_token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("users_invite_token_hash", "users")
    op.drop_column("users", "invite_expires_at")
    op.drop_column("users", "invite_token_hash")
