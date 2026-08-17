# SIRA + SEIL

**Buy software that fits the company you actually run.**

SIRA is the buyer agent. SEIL turns seller knowledge and public research into comparable, versioned product evidence. The current hackathon build is migrating their shared decision state to CockroachDB and running the agent path on AWS.

The key correctness claim is narrow: concurrent buyer, seller, and worker activity must not produce a stale, duplicated, or lost buying decision.

## Current build status

- The existing SIRA and SEIL product surfaces are retained.
- Previous sponsor-specific infrastructure has been removed from the active tree.
- CockroachDB schema, vector retrieval, serializable retries, fenced worker recovery,
  the typed cognitive kernel, and two isolated AgentCore runtime definitions are implemented.
- The complete deterministic path is verified locally against CockroachDB v26.2.3. Live
  Bedrock, AgentCore, Cockroach Cloud, Managed MCP, and AWS deployment evidence still requires
  valid cloud sessions and provisioned resources.
- Approved purchases can produce an immutable external payment handoff; SIRA never handles card data or claims payment success.

Implementation status and evidence are tracked in
[docs/flagship-platform-plan.md](docs/flagship-platform-plan.md). The current interface is a
frozen product boundary; see [docs/ui-preservation-review.md](docs/ui-preservation-review.md).
The explainable engineering record is in
[architecture decisions](docs/architecture-decisions.md), the
[threat model](docs/threat-model.md), and the
[typed tool guide](docs/tool-authoring-guide.md).

## Product boundaries

- [UI preservation agreement](docs/ui-preservation-review.md)

- Buyer context stays buyer-private.
- Seller drafts stay seller-private; only published buyer-safe projections cross into SIRA.
- Public research is visibly labeled and never silently becomes seller-attested evidence.
- Structured eligibility rules decide fit; vector retrieval only finds candidates.
- Purchase and contract actions require explicit human approval.

## Local development

Requirements: Python 3.12+, `uv`, Node.js 22+, and pnpm 11. On Windows, the local
launcher can use either Docker Desktop or WSL2 for CockroachDB.

```powershell
uv sync --all-extras
corepack pnpm install --frozen-lockfile
uv run sira-dev doctor --profile local
uv run sira-dev up --profile local
uv run sira-dev status --profile local
```

`sira-dev up` starts the loopback-only CockroachDB database, applies migrations and
role grants, then starts the API and restored web interface. Local mode does not
start cloud workers or perform external effects. Use `sira-dev logs`, `sira-dev
check`, and `sira-dev down` for the remaining lifecycle operations.

The destructive scenario reset is restricted to the exact local `sira_test`
database:

```powershell
uv run sira-scenario reset --scenario evidence-race
uv run sira-scenario run --scenario evidence-race
uv run sira-scenario verify --latest
```

## Provenance

SIRA and SEIL existed before this hackathon. The CockroachDB state layer, distributed vector retrieval, concurrent version validation, worker recovery, MCP inspection, and AWS deployment are new hackathon scope and will be disclosed precisely. See [SOURCE_PROVENANCE.md](SOURCE_PROVENANCE.md).

Apache-2.0 licensed. See [LICENSE](LICENSE).
