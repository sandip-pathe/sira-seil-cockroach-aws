# Setup

## Fast path

A developer with an OpenAI API key can reach a healthy local workflow in under 15 minutes.

```powershell
Copy-Item .env.example .env
uv sync --frozen --all-extras
corepack pnpm install --frozen-lockfile
uv run sira-dev doctor --profile local
uv run sira-dev up --profile local
uv run sira-dev status --profile local
```

Set `OPENAI_API_KEY` in `.env` before starting. The local lifecycle runs the web app,
API, Python qualification worker, and CockroachDB on the developer machine. The
worker polls the durable CockroachDB outbox directly. LangGraph retries transient OpenAI errors, while CockroachDB
continues to own durable workflow state and leases.

## Prerequisites

- Python version pinned by the active repository.
- `uv` version pinned by the active repository.
- Node.js and pnpm for the web application.
- Docker for local services and deterministic worker-stop testing.
- CockroachDB Cloud cluster or supported local CockroachDB image.
- OpenAI API key with access to the configured chat and embedding models.
- CockroachDB Cloud MCP client configuration for the operator/evaluator.

`doctor` reports missing prerequisites without printing credential values.

## Clean shutdown

```powershell
uv run sira-dev down
```

The command stops project-owned local processes only. It does not delete a cloud cluster, shared database, or another scenario.
