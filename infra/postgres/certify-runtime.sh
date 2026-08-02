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

PROBE_TABLE="__sira_ci_runtime_probe"
probe_created=false

bootstrap_psql() {
  psql \
    --no-psqlrc \
    --no-password \
    --quiet \
    --set=ON_ERROR_STOP=1 \
    --dbname="$APP_DATABASE" \
    "$@"
}

owner_psql() {
  PGUSER="$OWNER_ROLE" PGPASSWORD="$OWNER_PASSWORD" psql \
    --no-psqlrc \
    --no-password \
    --quiet \
    --set=ON_ERROR_STOP=1 \
    --set=expected_owner="$OWNER_ROLE" \
    --set=expected_runtime="$RUNTIME_ROLE" \
    --set=expected_database="$APP_DATABASE" \
    --set=expected_test_database="$TEST_DATABASE" \
    --dbname="$APP_DATABASE" \
    "$@"
}

runtime_psql() {
  PGUSER="$RUNTIME_ROLE" PGPASSWORD="$RUNTIME_PASSWORD" psql \
    --no-psqlrc \
    --no-password \
    --quiet \
    --set=ON_ERROR_STOP=1 \
    --set=expected_owner="$OWNER_ROLE" \
    --set=expected_runtime="$RUNTIME_ROLE" \
    --set=expected_database="$APP_DATABASE" \
    --set=expected_test_database="$TEST_DATABASE" \
    --dbname="$APP_DATABASE" \
    "$@"
}

cleanup() {
  status=$?
  trap - 0 HUP INT TERM
  if [ "$probe_created" = true ]; then
    bootstrap_psql >/dev/null 2>&1 <<SQL || true
DROP TABLE IF EXISTS public.$PROBE_TABLE;
SQL
  fi
  exit "$status"
}
trap cleanup 0 HUP INT TERM

# Create an IDENTITY sequence owned by the bootstrap login, then rerun the real
# reconciler. This proves reruns create/repair databases idempotently and that an
# owned sequence moves safely with its table instead of being altered independently.
bootstrap_psql >/dev/null <<SQL
BEGIN;
SELECT 1 / ((to_regclass('public.$PROBE_TABLE') IS NULL)::integer);
CREATE TABLE public.$PROBE_TABLE (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  organization_id text NOT NULL,
  payload text NOT NULL
);
ALTER TABLE public.$PROBE_TABLE ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.$PROBE_TABLE FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_access ON public.$PROBE_TABLE
  USING (organization_id = NULLIF(current_setting('app.organization_id', true), ''))
  WITH CHECK (organization_id = NULLIF(current_setting('app.organization_id', true), ''));
CREATE POLICY tenant_isolation ON public.$PROBE_TABLE
  AS RESTRICTIVE
  FOR ALL
  USING (organization_id = NULLIF(current_setting('app.organization_id', true), ''))
  WITH CHECK (organization_id = NULLIF(current_setting('app.organization_id', true), ''));
COMMIT;
SQL
probe_created=true

sh /bootstrap.sh >/dev/null

owner_psql >/dev/null <<SQL
SELECT 1 / ((
  session_user = :'expected_owner'
  AND current_user = :'expected_owner'
  AND EXISTS (
    SELECT 1
    FROM pg_roles
    WHERE rolname = current_user
      AND rolcanlogin
      AND NOT rolsuper
      AND NOT rolcreatedb
      AND NOT rolcreaterole
      AND NOT rolreplication
      AND rolbypassrls
  )
  AND NOT EXISTS (
    SELECT 1
    FROM pg_auth_members AS membership
    JOIN pg_roles AS member ON member.oid = membership.member
    WHERE member.rolname = current_user
  )
)::integer);

SELECT 1 / ((COUNT(*) = 2)::integer)
FROM pg_database AS database
JOIN pg_roles AS owner ON owner.oid = database.datdba
WHERE database.datname IN (:'expected_database', :'expected_test_database')
  AND owner.rolname = :'expected_owner';

SELECT 1 / ((pg_get_userbyid(relation.relowner) = :'expected_owner')::integer)
FROM pg_class AS relation
WHERE relation.oid = 'public.$PROBE_TABLE'::regclass;

SELECT 1 / ((pg_get_userbyid(relation.relowner) = :'expected_owner')::integer)
FROM pg_class AS relation
WHERE relation.oid = pg_get_serial_sequence('public.$PROBE_TABLE', 'id')::regclass;
SQL

# This is a new TCP login as the runtime role, not SET ROLE from an administrator.
# The assertions cover least-privilege ACLs plus tenant-aware CRUD and the linked
# IDENTITY sequence used by INSERT.
runtime_psql >/dev/null <<SQL
SELECT 1 / ((
  session_user = :'expected_runtime'
  AND current_user = :'expected_runtime'
  AND current_database() = :'expected_database'
)::integer);

SELECT 1 / ((COUNT(*) = 1)::integer)
FROM pg_roles
WHERE rolname = current_user
  AND rolcanlogin
  AND NOT rolsuper
  AND NOT rolcreatedb
  AND NOT rolcreaterole
  AND NOT rolreplication
  AND NOT rolbypassrls;

SELECT 1 / ((COUNT(*) = 0)::integer)
FROM pg_auth_members AS membership
JOIN pg_roles AS member ON member.oid = membership.member
WHERE member.rolname = current_user;

SELECT 1 / ((COUNT(*) = 0)::integer)
FROM pg_database AS database
JOIN pg_roles AS owner ON owner.oid = database.datdba
WHERE database.datname IN (:'expected_database', :'expected_test_database')
  AND owner.rolname = current_user;

SELECT 1 / ((
  has_database_privilege(current_user, current_database(), 'CONNECT')
  AND NOT has_database_privilege(current_user, current_database(), 'CREATE')
  AND NOT has_database_privilege(current_user, current_database(), 'TEMPORARY')
)::integer);

SELECT 1 / ((
  has_schema_privilege(current_user, 'public', 'USAGE')
  AND NOT has_schema_privilege(current_user, 'public', 'CREATE')
)::integer);

SELECT 1 / ((COUNT(*) = 0)::integer)
FROM pg_class AS relation
JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
WHERE namespace.nspname = 'public'
  AND pg_get_userbyid(relation.relowner) = current_user;

SELECT 1 / ((
  has_table_privilege(current_user, 'public.$PROBE_TABLE', 'SELECT')
  AND has_table_privilege(current_user, 'public.$PROBE_TABLE', 'INSERT')
  AND has_table_privilege(current_user, 'public.$PROBE_TABLE', 'UPDATE')
  AND has_table_privilege(current_user, 'public.$PROBE_TABLE', 'DELETE')
  AND NOT has_table_privilege(current_user, 'public.$PROBE_TABLE', 'TRUNCATE')
  AND NOT has_table_privilege(current_user, 'public.$PROBE_TABLE', 'REFERENCES')
  AND NOT has_table_privilege(current_user, 'public.$PROBE_TABLE', 'TRIGGER')
  AND NOT has_table_privilege(current_user, 'public.$PROBE_TABLE', 'MAINTAIN')
)::integer);

SELECT pg_get_serial_sequence('public.$PROBE_TABLE', 'id') AS probe_sequence \gset
SELECT 1 / ((
  has_sequence_privilege(current_user, :'probe_sequence', 'USAGE')
  AND has_sequence_privilege(current_user, :'probe_sequence', 'SELECT')
  AND NOT has_sequence_privilege(current_user, :'probe_sequence', 'UPDATE')
)::integer);

SELECT 1 / ((
  to_regclass('public.alembic_version') IS NOT NULL
  AND has_table_privilege(current_user, 'public.alembic_version', 'SELECT')
  AND NOT has_table_privilege(current_user, 'public.alembic_version', 'INSERT')
  AND NOT has_table_privilege(current_user, 'public.alembic_version', 'UPDATE')
  AND NOT has_table_privilege(current_user, 'public.alembic_version', 'DELETE')
)::integer);

SELECT 1 / ((
  to_regclass('public.organizations') IS NOT NULL
  AND NOT has_table_privilege(current_user, 'public.organizations', 'UPDATE')
  AND NOT has_table_privilege(current_user, 'public.organizations', 'DELETE')
)::integer);

SELECT 1 / ((COUNT(*) = 0)::integer)
FROM pg_proc AS routine
JOIN pg_namespace AS namespace ON namespace.oid = routine.pronamespace
WHERE namespace.nspname = 'public'
  AND has_function_privilege(current_user, routine.oid, 'EXECUTE');

BEGIN;
SELECT set_config('app.organization_id', 'org_runtime_certification', true);
INSERT INTO public.$PROBE_TABLE (organization_id, payload)
VALUES ('org_runtime_certification', 'created')
RETURNING id AS id \gset probe_
SELECT 1 / (((:probe_id)::bigint > 0)::integer);
SELECT 1 / ((
  currval(:'probe_sequence'::regclass) = (:probe_id)::bigint
)::integer);
SELECT 1 / ((COUNT(*) = 1)::integer)
FROM public.$PROBE_TABLE
WHERE id = (:probe_id)::bigint AND payload = 'created';

UPDATE public.$PROBE_TABLE
SET payload = 'updated'
WHERE id = (:probe_id)::bigint;
SELECT 1 / ((COUNT(*) = 1)::integer)
FROM public.$PROBE_TABLE
WHERE id = (:probe_id)::bigint AND payload = 'updated';

SELECT set_config('app.organization_id', 'org_other', true);
SELECT 1 / ((COUNT(*) = 0)::integer)
FROM public.$PROBE_TABLE
WHERE id = (:probe_id)::bigint;

SELECT set_config('app.organization_id', 'org_runtime_certification', true);
DELETE FROM public.$PROBE_TABLE WHERE id = (:probe_id)::bigint;
SELECT 1 / ((COUNT(*) = 0)::integer) FROM public.$PROBE_TABLE;
COMMIT;
SQL

echo "Restricted PostgreSQL runtime CRUD, RLS, sequence, ownership, and ACL checks passed."
