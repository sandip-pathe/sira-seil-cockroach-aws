#!/bin/sh
set -eu

: "${PGHOST:?PGHOST is required}"
: "${PGPORT:?PGPORT is required}"
: "${PGUSER:?PGUSER is required}"
: "${PGPASSWORD:?PGPASSWORD is required}"
: "${APP_DATABASE:?APP_DATABASE is required}"
: "${TEST_DATABASE:?TEST_DATABASE is required}"
: "${OWNER_ROLE:?OWNER_ROLE is required}"
: "${OWNER_PASSWORD:?OWNER_PASSWORD is required}"
: "${RUNTIME_ROLE:?RUNTIME_ROLE is required}"
: "${RUNTIME_PASSWORD:?RUNTIME_PASSWORD is required}"

validate_identifier() {
  case "$1" in
    ""|*[!A-Za-z0-9_]*|[0-9]*)
      echo "Invalid PostgreSQL identifier: $1" >&2
      exit 2
      ;;
  esac
  if [ "${#1}" -gt 63 ]; then
    echo "PostgreSQL identifier exceeds 63 bytes: $1" >&2
    exit 2
  fi
}

for identifier in \
  "$PGUSER" \
  "$APP_DATABASE" \
  "$TEST_DATABASE" \
  "$OWNER_ROLE" \
  "$RUNTIME_ROLE"
do
  validate_identifier "$identifier"
done

if [ "$PGUSER" = "$OWNER_ROLE" ] || \
   [ "$PGUSER" = "$RUNTIME_ROLE" ] || \
   [ "$OWNER_ROLE" = "$RUNTIME_ROLE" ]; then
  echo "PostgreSQL bootstrap, owner, and runtime roles must be distinct." >&2
  exit 2
fi

if [ "$APP_DATABASE" = "$TEST_DATABASE" ]; then
  echo "PostgreSQL application and test databases must be distinct." >&2
  exit 2
fi

reject_system_database() {
  case "$1" in
    [Pp][Oo][Ss][Tt][Gg][Rr][Ee][Ss]|\
    [Tt][Ee][Mm][Pp][Ll][Aa][Tt][Ee]0|\
    [Tt][Ee][Mm][Pp][Ll][Aa][Tt][Ee]1)
      echo "PostgreSQL application/test database cannot use system database name: $1" >&2
      exit 2
      ;;
  esac
}

reject_system_database "$APP_DATABASE"
reject_system_database "$TEST_DATABASE"

psql \
  --no-psqlrc \
  --no-password \
  --set=ON_ERROR_STOP=1 \
  --set=app_database="$APP_DATABASE" \
  --set=test_database="$TEST_DATABASE" \
  --set=bootstrap_role="$PGUSER" \
  --set=owner_role="$OWNER_ROLE" \
  --set=runtime_role="$RUNTIME_ROLE" \
  --dbname=postgres <<'SQL'
\getenv owner_password OWNER_PASSWORD
\getenv runtime_password RUNTIME_PASSWORD

SELECT format(
  'CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION BYPASSRLS',
  :'owner_role',
  :'owner_password'
)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'owner_role')
\gexec

SELECT format(
  'ALTER ROLE %I WITH LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION BYPASSRLS',
  :'owner_role',
  :'owner_password'
)
\gexec

SELECT format(
  'CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS',
  :'runtime_role',
  :'runtime_password'
)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'runtime_role')
\gexec

SELECT format('REVOKE %I FROM %I', parent.rolname, child.rolname)
FROM pg_auth_members AS membership
JOIN pg_roles AS parent ON parent.oid = membership.roleid
JOIN pg_roles AS child ON child.oid = membership.member
WHERE child.rolname IN (:'owner_role', :'runtime_role')
\gexec

SELECT format(
  'ALTER ROLE %I WITH LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS',
  :'runtime_role',
  :'runtime_password'
)
\gexec

SELECT format('CREATE DATABASE %I OWNER %I', :'app_database', :'owner_role')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'app_database')
\gexec

SELECT format('CREATE DATABASE %I OWNER %I', :'test_database', :'owner_role')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'test_database')
\gexec

SELECT format('ALTER DATABASE %I OWNER TO %I', :'app_database', :'owner_role')
\gexec

SELECT format('ALTER DATABASE %I OWNER TO %I', :'test_database', :'owner_role')
\gexec

SELECT format(
  'ALTER ROLE %I IN DATABASE %I SET search_path TO public, pg_catalog',
  role_name,
  database_name
)
FROM (VALUES (:'owner_role'), (:'runtime_role')) AS roles(role_name)
CROSS JOIN (VALUES (:'app_database'), (:'test_database')) AS databases(database_name)
\gexec
SQL

configure_database() {
  database_name="$1"

  psql \
    --no-psqlrc \
    --no-password \
    --set=ON_ERROR_STOP=1 \
    --set=database_name="$database_name" \
    --set=bootstrap_role="$PGUSER" \
    --set=owner_role="$OWNER_ROLE" \
    --set=runtime_role="$RUNTIME_ROLE" \
    --dbname="$database_name" <<'SQL'
SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC, %I', :'database_name', :'runtime_role')
\gexec
SELECT format(
  'GRANT CONNECT, CREATE, TEMPORARY ON DATABASE %I TO %I',
  :'database_name',
  :'owner_role'
)
\gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', :'database_name', :'runtime_role')
\gexec

SELECT format('ALTER SCHEMA public OWNER TO %I', :'owner_role')
\gexec
SELECT format('REVOKE ALL ON SCHEMA public FROM PUBLIC, %I', :'runtime_role')
\gexec
SELECT format('GRANT USAGE, CREATE ON SCHEMA public TO %I', :'owner_role')
\gexec
SELECT format('GRANT USAGE ON SCHEMA public TO %I', :'runtime_role')
\gexec

SELECT format(
  'ALTER %s %I.%I OWNER TO %I',
  CASE relation.relkind
    WHEN 'r' THEN 'TABLE'
    WHEN 'p' THEN 'TABLE'
    WHEN 'v' THEN 'VIEW'
    WHEN 'm' THEN 'MATERIALIZED VIEW'
    WHEN 'f' THEN 'FOREIGN TABLE'
  END,
  namespace.nspname,
  relation.relname,
  :'owner_role'
)
FROM pg_class AS relation
JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
WHERE namespace.nspname = 'public'
  AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
  AND pg_get_userbyid(relation.relowner) IN (:'bootstrap_role', :'runtime_role')
  AND NOT EXISTS (
      SELECT 1
      FROM pg_depend AS dependency
      WHERE dependency.classid = 'pg_class'::regclass
        AND dependency.objid = relation.oid
        AND dependency.deptype = 'e'
  )
ORDER BY relation.relkind, relation.relname
\gexec

-- SERIAL and IDENTITY sequences are linked to table columns. ALTER TABLE OWNER
-- moves them with the table; attempting ALTER SEQUENCE OWNER independently can
-- fail because PostgreSQL requires the linked table and sequence owners to match.
-- Reconcile only genuinely standalone, non-extension sequences here.
SELECT format(
  'ALTER SEQUENCE %I.%I OWNER TO %I',
  namespace.nspname,
  relation.relname,
  :'owner_role'
)
FROM pg_class AS relation
JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
WHERE namespace.nspname = 'public'
  AND relation.relkind = 'S'
  AND pg_get_userbyid(relation.relowner) IN (:'bootstrap_role', :'runtime_role')
  AND NOT EXISTS (
      SELECT 1
      FROM pg_depend AS dependency
      WHERE dependency.classid = 'pg_class'::regclass
        AND dependency.objid = relation.oid
        AND dependency.deptype IN ('a', 'i', 'e')
  )
ORDER BY relation.relname
\gexec

SELECT format(
  'ALTER ROUTINE %I.%I(%s) OWNER TO %I',
  namespace.nspname,
  routine.proname,
  pg_get_function_identity_arguments(routine.oid),
  :'owner_role'
)
FROM pg_proc AS routine
JOIN pg_namespace AS namespace ON namespace.oid = routine.pronamespace
WHERE namespace.nspname = 'public'
  AND pg_get_userbyid(routine.proowner) IN (:'bootstrap_role', :'runtime_role')
  AND NOT EXISTS (
      SELECT 1
      FROM pg_depend AS dependency
      WHERE dependency.classid = 'pg_proc'::regclass
        AND dependency.objid = routine.oid
        AND dependency.deptype = 'e'
  )
ORDER BY routine.proname
\gexec

SELECT format(
  'ALTER %s %I.%I OWNER TO %I',
  CASE type.typtype WHEN 'd' THEN 'DOMAIN' ELSE 'TYPE' END,
  namespace.nspname,
  type.typname,
  :'owner_role'
)
FROM pg_type AS type
JOIN pg_namespace AS namespace ON namespace.oid = type.typnamespace
WHERE namespace.nspname = 'public'
  AND type.typtype IN ('d', 'e')
  AND pg_get_userbyid(type.typowner) IN (:'bootstrap_role', :'runtime_role')
  AND NOT EXISTS (
      SELECT 1
      FROM pg_depend AS dependency
      WHERE dependency.classid = 'pg_type'::regclass
        AND dependency.objid = type.oid
        AND dependency.deptype = 'e'
  )
ORDER BY type.typname
\gexec

SELECT format('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC, %I', :'runtime_role')
\gexec
SELECT format(
  'REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC, %I',
  :'runtime_role'
)
\gexec
SELECT format('REVOKE ALL ON ALL ROUTINES IN SCHEMA public FROM PUBLIC, %I', :'runtime_role')
\gexec
SELECT format(
  'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO %I',
  :'runtime_role'
)
\gexec
SELECT format(
  'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO %I',
  :'runtime_role'
)
\gexec

SELECT format(
  'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public '
  'REVOKE ALL ON TABLES FROM PUBLIC, %I',
  :'owner_role',
  :'runtime_role'
)
\gexec
SELECT format(
  'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public '
  'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO %I',
  :'owner_role',
  :'runtime_role'
)
\gexec
SELECT format(
  'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public '
  'REVOKE ALL ON SEQUENCES FROM PUBLIC, %I',
  :'owner_role',
  :'runtime_role'
)
\gexec
SELECT format(
  'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public '
  'GRANT USAGE, SELECT ON SEQUENCES TO %I',
  :'owner_role',
  :'runtime_role'
)
\gexec
SELECT format(
  'ALTER DEFAULT PRIVILEGES FOR ROLE %I REVOKE ALL ON ROUTINES FROM PUBLIC, %I',
  :'owner_role',
  :'runtime_role'
)
\gexec

SELECT format(
  'REVOKE ALL ON TABLE public.alembic_version FROM %I',
  :'runtime_role'
)
WHERE to_regclass('public.alembic_version') IS NOT NULL
\gexec
SELECT format(
  'GRANT SELECT ON TABLE public.alembic_version TO %I',
  :'runtime_role'
)
WHERE to_regclass('public.alembic_version') IS NOT NULL
\gexec
SELECT format(
  'REVOKE UPDATE, DELETE ON TABLE public.organizations FROM %I',
  :'runtime_role'
)
WHERE to_regclass('public.organizations') IS NOT NULL
\gexec
SQL
}

configure_database "$APP_DATABASE"
configure_database "$TEST_DATABASE"

echo "PostgreSQL owner/runtime roles and databases are ready."
