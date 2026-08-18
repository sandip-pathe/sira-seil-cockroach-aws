# Setup

## Fast path

A developer with AWS Bedrock access can reach a healthy local workflow in under 15 minutes.

```powershell
Copy-Item .env.example .env
uv sync --frozen --all-extras
corepack pnpm install --frozen-lockfile
aws login --profile sira-hackathon
uv run sira-dev doctor --profile local
uv run sira-dev up --profile local
uv run sira-dev status --profile local
```

The local lifecycle keeps the web app, API, tools, and CockroachDB on the developer
machine while using the configured Bedrock runtime for cognitive turns.
Startup fails if that real provider cannot pass preflight; there is no user-facing
deterministic fallback.

Run the concurrency demonstration with:

```powershell
uv run sira-scenario reset --scenario evidence-race
uv run sira-scenario run --scenario evidence-race
uv run sira-scenario verify --latest
```

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

## Prerequisites

- Python version pinned by the active repository.
- `uv` version pinned by the active repository.
- Node.js and pnpm for the web application.
- Docker for local services and deterministic worker-stop testing.
- CockroachDB Cloud cluster or supported local CockroachDB image.
- AWS account with Bedrock model access.
- CockroachDB Cloud MCP client configuration for the operator/evaluator.

`doctor` reports missing prerequisites without printing credential values.

## Judge path

Use the anonymous guest sign-in for an isolated judge session. Follow the
[demo runbook](demo-runbook.md) for the evidence-change scenario.

The external MCP proof is a recorded/evaluator-operated path. Do not put shared MCP credentials in the public browser.

## Clean shutdown

```powershell
uv run sira-dev down
```

The command stops project-owned local processes only. It does not delete a cloud cluster, shared database, or another scenario.
