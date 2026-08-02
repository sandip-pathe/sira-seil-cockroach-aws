# Laptop backend handoff

Use branch `codex/postgres-fixes`. GitHub's disposable PostgreSQL 16 run already passed all
306 tests, migrations, forced-RLS checks, lint, typing, frozen contracts, and the current-tree
credential scan. The laptop work is for the real local runtime and provider sandboxes, not for
repeating the fixture implementation.

## 1. Checkout and install

```powershell
git fetch origin
git switch codex/postgres-fixes
git pull --ff-only
corepack prepare pnpm@11.9.0 --activate
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

Keep `.env` local and uncommitted. Do not paste provider credentials into issues, test output,
workflow inputs, or demo fixtures.

## 2. Certify local PostgreSQL

Create dedicated databases named `sira` and `sira_test`. Use an admin/owner login only for
migrations and the PostgreSQL tests. The running API and worker must use a separate
`NOSUPERUSER NOBYPASSRLS` role with the required table/schema privileges.

Set `DATABASE_ADMIN_URL` and `DATABASE_URL` in `.env`, then run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\migrate.ps1
$env:SIRA_TEST_DATABASE_ADMIN_URL = "postgresql+psycopg://<admin>:<url-encoded-password>@localhost:5432/sira_test"
.\.venv\Scripts\python.exe -m pytest tests\integration\test_persistence.py -m postgres -q
Remove-Item Env:SIRA_TEST_DATABASE_ADMIN_URL
```

Expected result: three PostgreSQL tests pass. They prove migration-to-head, demo seeding,
forced RLS, non-bypass runtime isolation, and buyer/bound-seller/unrelated-tenant engagement
visibility.

Still add one live concurrency test for `DB-02`: two independent PostgreSQL sessions must race
the same first idempotency claim and produce one canonical record, one replay response, no 500,
and no duplicate Purchase Intent. The current savepoint behavior is covered only by mocked/unit
tests.

## 3. Local smoke test

Start the API, then verify PostgreSQL is actually configured:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-api.ps1
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected: `status=ok`, `database=configured`, and `fixture_mode=true` for the labelled demo.
Run the reset and claimed buyer journey, refresh, and confirm decision/input hashes and state do
not change. Do not use the database owner login for this smoke test.

The laptop UI owner must also add the required `evaluation_mode` to the two
`DecisionRequestView` samples in `apps/web/components/decisions/decision-surfaces.tsx`; the
backend/client contract is already green.

## 4. Temporal and provider sandbox

Use the laptop's existing Docker/Temporal setup or a local Temporal development server and point
`TEMPORAL_ADDRESS` at it. The repository does not currently provision Temporal. Start the worker
only after PostgreSQL, Temporal, `WORKER_ORGANIZATION_IDS`, Prava, and controlled-merchant values
are configured:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-worker.ps1
```

Before claiming a live integration, complete these exact proofs:

- Senso: folder-scoped query key, exact content versions, human acceptance, and a fresh frozen
  source snapshot affect a decision while retrieved instructions remain untrusted data.
- Prava/merchant: create/revoke hosted session, pending/unknown reconciliation, duplicate retry,
  crash-after-charge, and paid-but-unfulfilled recovery without a duplicate charge.
- Refunds: full and partial refund reconciliation plus entitlement revocation; unresolved
  revocation must remain `COMPENSATION_REQUIRED`.
- Browser return: use a reachable HTTPS callback and verify no credential appears in browser
  payloads, persistence, logs, traces, Redis, or Temporal history.

If credentials or sandboxes are unavailable, keep the real adapters configured-but-blocked and
demo only the explicitly labelled deterministic fixture path. Never report a fixture payment,
refund, Senso result, or fulfillment as production success.
