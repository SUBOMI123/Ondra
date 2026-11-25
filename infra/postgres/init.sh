#!/bin/bash
# Runs once when the database volume is first created.
# Two roles: the owner (POSTGRES_USER) runs migrations and owns the tables; the app role is what the API
# connects as. The app role is NOT a superuser and has no BYPASSRLS, so row-level security always applies to it.
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE ROLE ondra_app LOGIN PASSWORD '${APP_DB_PASSWORD}' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO ondra_app;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS citext;
SQL
