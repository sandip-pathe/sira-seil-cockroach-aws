# SIRA + SEIL

SIRA and SEIL are B2B commerce agents: SIRA helps company buyers evaluate and purchase, while
SEIL helps sellers present evidence and sell to those buyers. This monorepo contains the
deterministic `consultco_v1` demo, exact-hash approval, constrained checkout, entitlement
verification, receipts, and staged Stackfile changes. PostgreSQL is canonical; development
fixtures are explicitly non-production.

`docs/BUILD_SPEC.md` controls this build sequence. `docs/PRD.md` controls product meaning
and security boundaries.

## Prerequisites on Windows

- Git
- Node.js 22 or newer with Corepack
- Python 3.12 or 3.13
- Docker Desktop for the recommended backend setup, or PostgreSQL 17 for a manual setup

## Recommended Docker backend

Docker provisions PostgreSQL, the administrative owner, the restricted runtime login, both
local databases, Alembic migrations, and the API in dependency order. From PowerShell:

```powershell
Set-Location <path-to-repository>
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up --build -d --wait api
docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/health
```

Health is ready only when the API connects directly as `sira_runtime`, that login is neither
superuser nor `BYPASSRLS`, it owns no tenant tables/schema/database, and PostgreSQL is at the
committed Alembic head. Compose publishes PostgreSQL and the API on `127.0.0.1` only.

If port 8000 is occupied, select another host port without changing the container:

```powershell
$env:SIRA_API_PORT = "18000"
docker compose up -d --wait api
Invoke-RestMethod http://127.0.0.1:18000/health
```

The defaults in `.env.example` are local-development credentials. Set
`POSTGRES_BOOTSTRAP_PASSWORD` before PostgreSQL initializes its named volume, and override
the owner/runtime passwords before sharing an environment. When changing an owner/runtime
role, password, or database name, update the paired `SIRA_DOCKER_DATABASE_ADMIN_URL` and
`SIRA_DOCKER_DATABASE_URL`; percent-encode passwords in URLs. Keep administrative URLs
limited to migration/test commands; the API and worker always use the separate runtime login.

On an initialized volume, `POSTGRES_BOOTSTRAP_PASSWORD` must continue to match the password
stored by PostgreSQL. To rotate it, first run the following command, complete the interactive
prompt, then update `.env`:

```powershell
docker compose exec postgres psql -U sira -d postgres -c '\password sira'
```

Changing only the environment value cannot rotate an existing PostgreSQL role.

`docker compose down` stops the stack and preserves PostgreSQL data. Do not add `--volumes`
unless you intentionally want to erase the local databases.

## Fresh setup without Docker

Run these commands from PowerShell after cloning or copying the repository:

```powershell
Set-Location <path-to-repository>
git switch core-backend
corepack prepare pnpm@11.9.0 --activate
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

The setup script installs the frozen Node and Python dependencies and creates `.env` from
`.env.example`. In pgAdmin, create a local application database named `sira` and a separate
test database named `sira_test`. Use different logins for runtime and administration:

```dotenv
DATABASE_URL=postgresql+asyncpg://<restricted-runtime>:<url-encoded-password>@localhost:5432/sira
DATABASE_ADMIN_URL=postgresql+psycopg://<owner-admin>:<url-encoded-password>@localhost:5432/sira
```

For a non-development deployment, also set `BROWSER_RETURN_SIGNING_KEY` to a stable,
cryptographically random value of at least 32 bytes. Rotating it invalidates outstanding
hosted-checkout returns. `WORKER_ORGANIZATION_IDS` is the comma-separated allowlist of tenants
whose RLS-scoped checkout outbox the worker may dispatch.

Apply all migrations:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\migrate.ps1
```

## Start locally

Open one PowerShell window for each process:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-api.ps1
```

```powershell
corepack pnpm dev:web
```

The API is at `http://127.0.0.1:8000`, interactive API documentation is at
`http://127.0.0.1:8000/docs`, and the intentionally minimal web shell is at
`http://localhost:3000`.

The deterministic development flow runs with `DEVELOPMENT_FIXTURE_MODE=true`. Only the labelled
fixture quote uses its fixed as-of time so it cannot expire merely because the demo is run later;
approval, provider-session, browser-return, reversal, and outcome clocks continue to use real
UTC time. Start the durable checkout worker only after Temporal and the real provider settings
are configured:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-worker.ps1
```

The equivalent container is opt-in and intentionally fails closed when Temporal or provider
configuration is missing:

```powershell
docker compose --profile worker up -d worker
```

Compose passes configured Prava and controlled-merchant values to the API so hosted-session
creation can run, and to the optional worker for checkout execution. The worker still requires
a reachable Temporal service; the repository deliberately does not start one.

## Verify

Run every environment-independent check:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check.ps1
```

This runs Python lint and formatting checks, strict type checking, tests with the 75%
coverage gate, OpenAPI drift detection, web/client checks, and a credential scan. With no
database or provider credentials, deterministic tests still run and the live PostgreSQL
test is reported as skipped.

To run all eight live PostgreSQL tests against Docker's dedicated test database:

```powershell
$env:SIRA_TEST_DATABASE_ADMIN_URL = "postgresql+psycopg://sira:<url-encoded-bootstrap-password>@127.0.0.1:5432/sira_test"
.\.venv\Scripts\python.exe -m pytest tests\integration\test_persistence.py -m postgres -q
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check.ps1
Remove-Item Env:SIRA_TEST_DATABASE_ADMIN_URL
```

The test refuses non-PostgreSQL URLs and any database not named `sira_test` or
`sira_test_*`. It migrates and writes fixtures but never creates or drops a database.

Running the repository directly on the PostgreSQL laptop is the simplest arrangement. If
this machine must connect to PostgreSQL on that laptop, use an SSH or Tailscale tunnel and
point both database URLs at the tunnel; do not expose port 5432 to the public internet.

## Live integration setup still required

Real execution requires the empty provider values in `.env.example`: four separately
scoped Senso keys, Prava hosted-checkout configuration, controlled-merchant credentials,
an OpenAI key for the optional agent adapter, and Temporal. A production identity adapter
must also be supplied by the deployment. Fixture adapters never claim production success,
and Prava's one-time payment credential exists only inside the isolated checkout call.

When the OpenAPI surface changes, regenerate and verify the frozen contract and client:

```powershell
.\.venv\Scripts\python.exe scripts\generate_openapi.py
corepack pnpm generate:client
.\.venv\Scripts\python.exe scripts\generate_openapi.py --check
corepack pnpm check:web
```
