"""Where a client's name came from (founder, 2026-11-28): so a name Ondra heard on a call, which speech recognition
can misspell, is flagged for staff to check until someone confirms or fixes it.

contacts.name_source: 'call' (Ondra heard it on a phone call), 'typed' (the customer wrote it), 'staff' (a person
entered or confirmed it), or null (imported, from a channel profile, or from before this column).

Revision ID: 0021
Revises: 0020
"""

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contacts", sa.Column("name_source", sa.String(10), nullable=True))
    op.create_check_constraint("contacts_name_source", "contacts", "name_source IN ('call', 'typed', 'staff')")


def downgrade() -> None:
    op.drop_constraint("contacts_name_source", "contacts", type_="check")
    op.drop_column("contacts", "name_source")
