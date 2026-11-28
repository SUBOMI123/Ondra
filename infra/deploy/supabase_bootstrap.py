"""Prepare a Supabase project for Ondra, the way infra/postgres/init.sh prepares the local database.

    uv run python infra/deploy/supabase_bootstrap.py --project <ref> --fly-app ondra-api-staging [--fly-app ondra-voice-staging]
    (The first --fly-app runs migrations and gets the owner URL too; the others get the app role only.)

1. Through Supabase's Management API (POST /v1/projects/{ref}/database/query, which runs as `postgres`): install the
   extensions Ondra needs, then create two roles with freshly generated passwords:
     ondra_owner  runs migrations and owns the tables; BYPASSRLS, like the local owner (the SECURITY DEFINER sign-in
                  and tenant lookups, and the seed, run as the owner under FORCE ROW LEVEL SECURITY)
     ondra_app    what the API, job worker and voice worker connect as: no superuser, no BYPASSRLS, so row-level
                  security always applies
   Verified 2026-11-27 on the staging project: `postgres` is not a superuser but has CREATEROLE and BYPASSRLS, and
   vector, citext and btree_gist are available.
2. Hands DATABASE_URL and MIGRATIONS_DATABASE_URL to each Fly app with `fly secrets import` (read from stdin), so
   the passwords never touch the terminal, a file or git. Running it again rotates both passwords.

The Supabase access token is injected by the session's network proxy (or set SUPABASE_ACCESS_TOKEN when run
elsewhere). Connection: Supabase's direct connection (db.<ref>.supabase.co:5432). Per Supabase's docs it's the one
for a persistent backend on IPv6 (Fly Machines have IPv6), and unlike the transaction pooler it keeps LISTEN/NOTIFY,
which the dashboard's live updates use.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import urllib.request

API = "https://api.supabase.com/v1"


def run_sql(ref: str, sql: str) -> list:
    req = urllib.request.Request(
        f"{API}/projects/{ref}/database/query", data=json.dumps({"query": sql}).encode(), method="POST",
        headers={"Authorization": f"Bearer {os.getenv('SUPABASE_ACCESS_TOKEN', 'proxy-injected')}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"[]")


def role_sql(name: str, password: str, owner: bool) -> str:
    attrs = "LOGIN BYPASSRLS NOSUPERUSER NOCREATEDB NOCREATEROLE" if owner else \
        "LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE"
    # The password is generated here (hex: nothing to escape) and only ever travels inside this request.
    return (f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{name}') THEN "
            f"ALTER ROLE {name} {attrs} PASSWORD '{password}'; ELSE CREATE ROLE {name} {attrs} PASSWORD '{password}'; "
            f"END IF; END $$;")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--project", required=True, help="Supabase project ref, e.g. sbesiusjfltienbbieyv")
    p.add_argument("--fly-app", action="append", default=[], help="Fly app to give the database secrets (repeatable)")
    p.add_argument("--database", default="postgres")
    a = p.parse_args()

    owner_pw, app_pw = secrets.token_hex(24), secrets.token_hex(24)
    run_sql(a.project, "CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS citext; "
                       "CREATE EXTENSION IF NOT EXISTS btree_gist;")
    run_sql(a.project, role_sql("ondra_owner", owner_pw, owner=True))
    run_sql(a.project, role_sql("ondra_app", app_pw, owner=False))
    run_sql(a.project, f"GRANT CONNECT ON DATABASE {a.database} TO ondra_owner, ondra_app; "
                       "GRANT USAGE, CREATE ON SCHEMA public TO ondra_owner; GRANT USAGE ON SCHEMA public TO ondra_app;")
    check = run_sql(a.project, "SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname IN ('ondra_owner', 'ondra_app') "
                               "ORDER BY rolname")
    by = {r["rolname"]: r for r in check}
    assert by["ondra_app"]["rolbypassrls"] is False and by["ondra_app"]["rolsuper"] is False, "ondra_app must not bypass RLS"
    assert by["ondra_owner"]["rolbypassrls"] is True, "ondra_owner must bypass RLS (migrations and the seed run as it)"
    print("roles ready:", ", ".join(f"{r['rolname']} (bypass RLS: {r['rolbypassrls']})" for r in check))

    host = f"db.{a.project}.supabase.co"
    urls = (f"DATABASE_URL=postgresql+asyncpg://ondra_app:{app_pw}@{host}:5432/{a.database}?ssl=require\n"
            f"MIGRATIONS_DATABASE_URL=postgresql+asyncpg://ondra_owner:{owner_pw}@{host}:5432/{a.database}?ssl=require\n")
    for app in a.fly_app:
        # Only the API app runs migrations (its release_command); every other app gets the app role alone.
        mine = urls if app == a.fly_app[0] else urls.splitlines(keepends=True)[0]
        r = subprocess.run(["fly", "secrets", "import", "--stage", "-a", app], input=mine, text=True,
                           capture_output=True, check=False)
        if r.returncode:
            sys.exit(f"fly secrets import failed for {app}: {r.stderr.strip()}")
        print(f"database secrets staged on {app} (applied on its next deploy)")


if __name__ == "__main__":
    main()
