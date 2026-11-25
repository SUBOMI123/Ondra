"""Tenant isolation with row-level security.

Every tenant-scoped table gets RLS enabled and FORCED (so even the table owner is filtered when it isn't a
superuser), with one policy: rows are visible and writable only when tenant_id equals the tenant set for the
current transaction (`SET LOCAL app.tenant_id`). With no tenant set, nothing is visible.

The API connects as `ondra_app` (no superuser, no BYPASSRLS). Signing in needs to find a user by email before the
tenant is known, so that one lookup goes through a SECURITY DEFINER function that returns only what sign-in needs.

Revision ID: 0002
Revises: 0001
"""

from alembic import op

from ondra_core.models import TENANT_TABLES

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

APP_ROLE = "ondra_app"


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_current_tenant() RETURNS uuid
        LANGUAGE sql STABLE AS $$ SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid $$
        """
    )
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING (tenant_id = app_current_tenant()) WITH CHECK (tenant_id = app_current_tenant())"
        )

    op.execute("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenants FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_self ON tenants USING (id = app_current_tenant()) WITH CHECK (id = app_current_tenant())")

    # The app role can read and change dealer data (within its tenant), but can't create tenants, and can only
    # append to the audit log.
    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
    op.execute(f"GRANT SELECT, UPDATE ON tenants TO {APP_ROLE}")
    for table in TENANT_TABLES:
        if table == "audit_log":
            op.execute(f"GRANT SELECT, INSERT ON audit_log TO {APP_ROLE}")
        else:
            op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {APP_ROLE}")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION auth_find_user(p_email citext)
        RETURNS TABLE (id uuid, tenant_id uuid, role text, password_hash text, active boolean)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
          SELECT u.id, u.tenant_id, u.role::text, u.password_hash, u.active FROM users u WHERE u.email = p_email
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION auth_find_user(citext) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION auth_find_user(citext) TO {APP_ROLE}")

def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS auth_find_user(citext)")
    for table in (*TENANT_TABLES, "tenants"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_self ON tenants")
    op.execute("DROP FUNCTION IF EXISTS app_current_tenant()")
