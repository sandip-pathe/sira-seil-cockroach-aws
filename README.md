# SIRA + SEIL

SIRA + SEIL is a company-aware decision and procurement control plane. This monorepo
contains the deterministic `consultco_v1` demo, exact-hash approval, constrained checkout,
entitlement verification, receipts, and staged Stackfile changes. PostgreSQL is canonical;
development fixtures are explicitly non-production.

`docs/BUILD_SPEC.md` controls this build sequence. `docs/PRD.md` controls product meaning
and security boundaries.

## Prerequisites on Windows

- Git
- Node.js 22 or newer with Corepack
- Python 3.12 or 3.13
- PostgreSQL 17 on the laptop; Docker Desktop is optional

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
test database named `sira_test`. Update these two values in `.env` for the application role:

```dotenv
DATABASE_URL=postgresql+asyncpg://<user>:<url-encoded-password>@localhost:5432/sira
DATABASE_ADMIN_URL=postgresql+psycopg://<user>:<url-encoded-password>@localhost:5432/sira
```

For a non-development deployment, also set `BROWSER_RETURN_SIGNING_KEY` to a stable,
cryptographically random value of at least 32 bytes. Rotating it invalidates outstanding
hosted-checkout returns. `WORKER_ORGANIZATION_IDS` is the comma-separated allowlist of tenants
whose RLS-scoped checkout outbox the worker may dispatch.

Apply all migrations:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\migrate.ps1
```

Docker remains an optional way to supply PostgreSQL. If its engine is available, the
equivalent database startup is:

```powershell
docker compose up -d postgres
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

The deterministic development flow runs with `DEVELOPMENT_FIXTURE_MODE=true`. Start the
durable checkout worker only after Temporal and the provider settings are configured:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-worker.ps1
```

## Verify

Run every environment-independent check:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check.ps1
```

This runs Python lint and formatting checks, strict type checking, tests with the 75%
coverage gate, OpenAPI drift detection, web/client checks, and a credential scan. With no
database or provider credentials, deterministic tests still run and the live PostgreSQL
test is reported as skipped.

To run the migration and row-level-security test against the laptop's dedicated database:

```powershell
$env:SIRA_TEST_DATABASE_ADMIN_URL = "postgresql+psycopg://<user>:<url-encoded-password>@localhost:5432/sira_test"
.\.venv\Scripts\python.exe -m pytest tests\integration\test_persistence.py -m postgres
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
