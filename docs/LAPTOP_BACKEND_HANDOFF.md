# Laptop backend handoff

The merged backend baseline is `core-backend`. This follow-up makes the previously untested
PostgreSQL and Docker path reproducible. Keep `.env` private and uncommitted; provider keys are
not required for the database/API proof.

## 1. Start the Docker backend

Start Docker Desktop, then run from PowerShell:

```powershell
Set-Location <path-to-repository>
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose config --quiet
docker compose up --build -d --wait api
docker compose ps -a
Invoke-RestMethod http://127.0.0.1:8000/health
```

If another process owns port 8000:

```powershell
$env:SIRA_API_PORT = "18000"
docker compose up -d --wait api
Invoke-RestMethod http://127.0.0.1:18000/health
```

Compose executes this dependency chain:

```text
PostgreSQL healthy
  -> owner/runtime/database bootstrap
  -> Alembic upgrade to head
  -> post-migration ownership and ACL reconciliation
  -> API readiness through the direct runtime login
```

The bootstrap is rerunnable and repairs the legacy `sira`-owned volume as well as a new volume,
provided `POSTGRES_BOOTSTRAP_PASSWORD` still matches the credential stored in that initialized
cluster. Set it before first initialization. To rotate it later, use the current credential:

```powershell
docker compose exec postgres psql -U sira -d postgres -c '\password sira'
```

Complete the interactive prompt and then update `.env`; changing only the environment value
does not alter the stored PostgreSQL password.

Raw owner/runtime passwords are safely passed to the role bootstrap, but connection URLs need
percent-encoded passwords. Keep `SIRA_DOCKER_DATABASE_ADMIN_URL` and
`SIRA_DOCKER_DATABASE_URL` synchronized whenever a role, password, or database name changes.

The bootstrap creates:

- `sira_owner`: non-superuser administrative/migration login with `BYPASSRLS`, `NOCREATEDB`,
  and `NOCREATEROLE`; never use it in `DATABASE_URL`;
- `sira_runtime`: direct API/worker login with `NOSUPERUSER`, `NOBYPASSRLS`, no role
  memberships, no database/schema/table ownership, and only application privileges;
- `sira` and `sira_test`, both owned by `sira_owner`.

The API health check rejects superuser, `BYPASSRLS`, assumed-role, owner/member-of-owner, stale
Alembic head, and unavailable database configurations. The Docker API runs as a non-root user
with a read-only root filesystem, all Linux capabilities dropped, and `no-new-privileges`.

## 2. Certify PostgreSQL

The PostgreSQL test harness creates and removes ephemeral restricted roles, so its URL must use
the bootstrap superuser and still point only at the dedicated test database. Alembic continues
to use the narrower owner login:

```powershell
$env:SIRA_TEST_DATABASE_ADMIN_URL = "postgresql+psycopg://sira:<url-encoded-bootstrap-password>@127.0.0.1:5432/sira_test"
.\.venv\Scripts\python.exe -m pytest tests\integration\test_persistence.py -m postgres -q
$env:DATABASE_ADMIN_URL = "postgresql+psycopg://sira_owner:<url-encoded-owner-password>@127.0.0.1:5432/sira"
.\.venv\Scripts\python.exe -m alembic check
Remove-Item Env:DATABASE_ADMIN_URL
docker compose --profile certify run --rm postgres-certify
```

Expected result: `8 passed, 4 deselected`, followed by `No new upgrade operations detected`.
Keep `SIRA_TEST_DATABASE_ADMIN_URL` set through the full verification in section 4; otherwise
the PostgreSQL cases are skipped and the claimed full-test count is not reproducible. The
Compose certification then logs in directly as `sira_runtime`, exercises tenant-aware CRUD and
an owned IDENTITY sequence, and rejects excessive runtime ACLs.
The tests prove:

- migration to the exact head, fixture reset/seed, JSONB model parity, and forced RLS;
- a real restricted login cannot read or write across tenants;
- buyer/bound-seller engagement visibility, unrelated-tenant denial, and seller inability to
  forge buyer-owned consent/contact fields;
- two independent PostgreSQL sessions racing the first idempotency claim return one canonical
  Purchase Intent and replay response without a 500 or duplicate;
- repeat demo reset succeeds after reversal and outcome records exist;
- owner/admin readiness is rejected while a direct restricted runtime login is accepted.

## 3. Existing and fresh-volume proof

Normal startup preserves the named volume:

```powershell
docker compose down
docker compose up -d --wait api
```

To certify a new isolated volume without touching the normal project, use a distinct project
name and ports:

```powershell
$env:POSTGRES_PORT = "55432"
$env:SIRA_API_PORT = "18001"
docker compose -p sira-cert up -d --wait api
Invoke-RestMethod http://127.0.0.1:18001/health
```

Only remove that disposable database when you explicitly intend to erase it:

```powershell
docker compose -p sira-cert down --volumes --remove-orphans
Remove-Item Env:POSTGRES_PORT
Remove-Item Env:SIRA_API_PORT
```

## 4. Full backend verification

```powershell
.\.venv\Scripts\python.exe -m ruff check python services tests scripts
.\.venv\Scripts\python.exe -m ruff format --check python services tests scripts
.\.venv\Scripts\python.exe -m mypy python services
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\generate_openapi.py --check
.\.venv\Scripts\python.exe scripts\credential_scan.py --current-tree-only
Remove-Item Env:SIRA_TEST_DATABASE_ADMIN_URL
```

Current local result: `314 passed`; Ruff, strict mypy, frozen OpenAPI, Compose validation,
Alembic drift check, and the credential scan are also clean.

Deterministic API tests explicitly ignore private provider values in the laptop `.env`. Only
the labelled fixture quote uses its frozen as-of time; approval, provider-session,
browser-return, reversal, outcome, production, and direct service/worker paths use real UTC.

## 5. Temporal and live-provider certification remain separate

The worker is deliberately an opt-in profile. The repository still does not provision a
Temporal server and no live Senso, Prava, merchant, refund, entitlement, or HTTPS browser-return
claim is certified by the Docker/API proof.

Compose passes configured Prava and controlled-merchant settings to both the API and worker.
This enables the API to create hosted sessions and the worker to execute checkout only after a
real Temporal endpoint and all provider values are configured:

```powershell
$env:DOCKER_TEMPORAL_ADDRESS = "<reachable-temporal-host>:7233"
docker compose --profile worker up -d worker
docker compose logs -f worker
```

Without those settings, leave the worker stopped. Never report fixture payment, refund,
fulfillment, Senso retrieval, or browser return as a live provider success.
