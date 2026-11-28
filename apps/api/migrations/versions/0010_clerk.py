"""Clerk: a dealership is a Clerk Organization, a person a Clerk user. Roles and permissions stay here.

Revision ID: 0010
Revises: 0009
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

APP_ROLE = "ondra_app"


def upgrade() -> None:
    op.add_column("tenants", sa.Column("clerk_org_id", sa.String(64), nullable=True))
    op.create_unique_constraint("tenants_clerk_org_id_key", "tenants", ["clerk_org_id"])
    op.add_column("users", sa.Column("clerk_user_id", sa.String(64), nullable=True))
    op.create_unique_constraint("users_clerk_user_id_key", "users", ["clerk_user_id"])
    # Before a request knows its dealership, it may learn only which dealership owns a Clerk Organization:
    # the same narrow, cross-tenant lookup as auth_find_user and channel_find_tenant.
    op.execute("""
        CREATE OR REPLACE FUNCTION tenant_for_clerk_org(p_org text) RETURNS uuid
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
          SELECT t.id FROM tenants t WHERE t.clerk_org_id = p_org
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION tenant_for_clerk_org(text) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION tenant_for_clerk_org(text) TO {APP_ROLE}")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS tenant_for_clerk_org(text)")
    op.drop_constraint("users_clerk_user_id_key", "users")
    op.drop_column("users", "clerk_user_id")
    op.drop_constraint("tenants_clerk_org_id_key", "tenants")
    op.drop_column("tenants", "clerk_org_id")
