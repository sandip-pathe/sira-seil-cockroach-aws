# Setup contract

Status: repository setup and verification are implemented; the unified `sira-dev`/`sira-demo`
operator interface below remains a target convenience layer.

## Fast path

A developer with existing CockroachDB Cloud and AWS access should reach a healthy synthetic workflow in under 15 minutes.

Current implemented local verification path:

```powershell
uv sync --frozen --all-extras
docker compose up -d --wait cockroach
$env:SIRA_TEST_DATABASE_URL = "cockroachdb+asyncpg://sira_app@127.0.0.1:26257/sira?ssl=disable"
$env:SIRA_TEST_WORKER_DATABASE_URL = "cockroachdb+asyncpg://sira_worker_app@127.0.0.1:26257/sira?ssl=disable"
$env:SIRA_TEST_CATALOG_DATABASE_URL = "cockroachdb+asyncpg://sira_catalog_app@127.0.0.1:26257/sira?ssl=disable"
uv run pytest tests/cockroach_integration -q
powershell -ExecutionPolicy Bypass -File scripts/check.ps1
pnpm build:web
```

Target unified wrapper once the hosted scenario controller exists:

```powershell
uv sync --frozen --all-extras
uv run sira-dev doctor --profile local
uv run sira-dev up --profile local
uv run sira-demo reset --scenario evidence-race
uv run sira-demo run --scenario evidence-race
uv run sira-demo verify --latest
```

The local lifecycle keeps the web app, API, tools, and CockroachDB on the developer
machine while using the configured Bedrock or AgentCore runtime for cognitive turns.
Startup fails if that real provider cannot pass preflight; there is no user-facing
deterministic fallback.

Expected final output:

```text
Scenario          evidence-race
Seller correction EU available -> US-only
Stale attempt     INVALIDATED / no decision
Worker recovery   standby worker resumed
Duplicate event   1 effect
Current decision  1 / uses v2
SQL integrity     PASS
Next              run external MCP verification
```

Fresh cloud provisioning is a separate guide and is not included in the 15-minute target.

## Prerequisites

- Python version pinned by the active repository.
- `uv` version pinned by the active repository.
- Node/pnpm only if the web workspace is not wrapped by the unified task interface.
- Docker for local services and deterministic worker-stop testing.
- CockroachDB Cloud cluster or supported local CockroachDB image.
- AWS account with Bedrock model access.
- CockroachDB Cloud MCP client configuration for the operator/evaluator.

`doctor` must name every missing prerequisite and print one next action. It must never print a credential value.

## Judge path

The public app provides an isolated guest scenario and an explicit `Start evidence-change demo` control. A judge should reach the scenario in under two minutes without configuring shared credentials.

The external MCP proof is a recorded/evaluator-operated path. Do not put shared MCP credentials in the public browser.

## Clean shutdown

```powershell
uv run sira-dev down
```

The command stops project-owned local processes only. It does not delete a cloud cluster, shared database, or another scenario.
