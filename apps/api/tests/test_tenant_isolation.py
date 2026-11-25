"""Tenant isolation is enforced by Postgres row-level security, not just by the API. These tests talk to the
database as the app role directly, the way a buggy query would."""

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError, ProgrammingError

from ondra_api.db import no_tenant_session, tenant_session
from ondra_core.models import TENANT_TABLES, Contact, Vehicle


async def test_every_table_with_tenant_id_has_forced_rls(database):
    async with no_tenant_session() as db:
        rows = (await db.execute(text(
            """
            SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind = 'r'
              AND EXISTS (SELECT 1 FROM information_schema.columns col
                          WHERE col.table_name = c.relname AND col.column_name = 'tenant_id')
            """
        ))).all()
    assert {r.relname for r in rows} == set(TENANT_TABLES)
    assert all(r.relrowsecurity and r.relforcerowsecurity for r in rows), rows


async def test_no_tenant_set_sees_nothing(database):
    async with no_tenant_session() as db:
        for table in TENANT_TABLES:
            assert (await db.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one() == 0, table
        assert (await db.execute(text("SELECT count(*) FROM tenants"))).scalar_one() == 0


async def test_tenant_sees_only_its_rows(database):
    async with tenant_session(database["a"]) as db:
        assert (await db.execute(select(func.count()).select_from(Contact))).scalar_one() == 30
        assert (await db.execute(select(Contact).where(Contact.display_name == "Only In Tenant B"))).first() is None
        assert {t for (t,) in (await db.execute(select(Vehicle.tenant_id).distinct())).all()} == {database["a"]}
    async with tenant_session(database["b"]) as db:
        assert (await db.execute(select(func.count()).select_from(Contact))).scalar_one() == 1


async def test_cannot_insert_into_another_tenant(database):
    with pytest.raises((DBAPIError, ProgrammingError), match="row-level security"):
        async with tenant_session(database["a"]) as db:
            db.add(Contact(tenant_id=database["b"], display_name="Smuggled"))
            await db.flush()


async def test_cannot_update_or_delete_another_tenants_rows(database):
    async with tenant_session(database["b"]) as db:
        b_contact = (await db.execute(select(Contact.id))).scalar_one()
    async with tenant_session(database["a"]) as db:
        res = await db.execute(update(Contact).where(Contact.id == b_contact).values(display_name="Changed"))
        assert res.rowcount == 0
        res = await db.execute(text("DELETE FROM contacts WHERE id = :i"), {"i": b_contact})
        assert res.rowcount == 0
    async with tenant_session(database["b"]) as db:
        assert (await db.execute(select(Contact.display_name))).scalar_one() == "Only In Tenant B"


async def test_cannot_move_a_row_to_another_tenant(database):
    with pytest.raises((DBAPIError, ProgrammingError), match="row-level security"):
        async with tenant_session(database["a"]) as db:
            await db.execute(update(Contact).where(Contact.display_name == "Kevin Lee").values(tenant_id=database["b"]))


async def test_app_role_cannot_switch_off_rls_or_become_owner(database):
    with pytest.raises((DBAPIError, ProgrammingError)):
        async with no_tenant_session() as db:
            await db.execute(text("SET ROLE ondra_owner"))
    async with no_tenant_session() as db:
        await db.execute(text("SET row_security = off"))
        # With row_security off, Postgres raises instead of silently filtering, so nothing leaks either way.
        with pytest.raises((DBAPIError, ProgrammingError)):
            await db.execute(text("SELECT count(*) FROM contacts"))


async def test_tenant_setting_does_not_leak_between_transactions(database):
    async with tenant_session(database["a"]) as db:
        assert (await db.execute(select(func.count()).select_from(Contact))).scalar_one() == 30
    for _ in range(5):  # pooled connections come back without a tenant
        async with no_tenant_session() as db:
            assert (await db.execute(select(func.count()).select_from(Contact))).scalar_one() == 0
