# Developer and evaluator experience contract

Status: reviewed; changes folded into the build package.

## Personas

### Future build agent

Needs one authoritative reading order, locked decisions, exact next milestone, and a clear distinction between planned and implemented work.

### Hackathon evaluator

Needs a public app that works, a short README, a one-command verification path, synthetic-data disclosure, exact sponsor-tool use, and understandable failure states.

### Developer

Needs safe setup for CockroachDB Cloud, Bedrock, ECS, and MCP without copying secrets into source or guessing which services must run.

## Target first success

Within 15 minutes of cloning, a developer with existing CockroachDB Cloud and AWS access should be able to:

1. validate prerequisites and configuration;
2. connect to a disposable CockroachDB database;
3. seed synthetic buyer context and public catalog evidence;
4. run one SIRA evaluation;
5. see one versioned decision and source references;
6. run the integrity check.

Cloud deployment and the full evidence-race demo are separate milestones.

## Command interface to build

Use one cross-platform Python task surface, with PowerShell wrappers only where needed:

```text
uv run sira-dev doctor --profile local
uv run sira-dev up --profile local
uv run sira-dev status
uv run sira-demo reset --scenario evidence-race
uv run sira-demo run --scenario evidence-race
uv run sira-demo verify --latest
uv run sira-dev logs --trace <trace-id>
uv run sira-dev down
```

The implementation may wrap existing package commands, but the README exposes this one vocabulary.

## Doctor output

Return a short table and nonzero exit on required failure:

```text
CockroachDB SQL       READY   cluster and database matched
Schema                READY   expected migration head
Tenant policies       READY   runtime role cannot bypass
Vector indexes        READY   context and catalog indexes found
Bedrock embeddings    READY   model and 1024 dimensions matched
Workers               READY   2 active
MCP scope             READY   demo cluster, configured read-only
Fixture fallback      OFF     hosted-safe
```

Do not print connection strings, tokens, API keys, raw prompts, or tenant content.

## Safe environment contract

`.env.example` contains names and comments only. Split scopes:

- application SQL credentials;
- migration/operator credentials;
- read-only MCP credentials/config;
- AWS region and Bedrock model;
- Firebase/public frontend settings;
- demo-mode flag.

Hosted secrets belong in AWS-managed secret configuration. Frontend receives no database, MCP, or Bedrock secret.

## Error copy

| Condition | User/developer copy | Next action |
|---|---|---|
| Database unavailable | `Decision state is unavailable. No fallback result was used.` | Check database readiness; retry |
| Schema mismatch | `Database schema does not match this build.` | Run the named migration command |
| RLS/authority denial | `This account cannot access that record.` | Check identity and organization; no existence details |
| Bedrock denied | `Evidence could not be embedded. No vector was stored.` | Check model access and AWS region |
| Stale vector | `Some evidence changed and is being refreshed.` | Re-embed; continue only with enough current evidence |
| Serialization retries exhausted | `The decision changed too quickly to finish safely.` | Retry the mission; do not reuse old output |
| Lease lost | `Another worker resumed this evaluation.` | Stale worker stops; no user action |
| MCP scope/auth failure | `External integrity inspection could not reach the scoped demo cluster.` | Fix MCP identity/scope; recommendation is unchanged |
| Integrity mismatch | `Integrity check failed: <named invariant>.` | Do not claim a verified demo; inspect exact attempt |

## Documentation order

Public README should be short:

1. product and 30-second story;
2. one outcome-changing demo GIF/screenshot;
3. why CockroachDB is causal;
4. architecture;
5. quickstart;
6. `doctor`, `demo`, and expected output;
7. security and synthetic-data boundary;
8. exact CockroachDB/AWS tool use;
9. provenance;
10. deeper links.

Do not rewrite the prior submission README by replacing nouns. Write it from the product story and verified build.

## Developer journey

| Stage | Required experience |
|---|---|
| Discover | Understand buyer value and the evidence-correction story in 30 seconds |
| Evaluate | Open hosted demo, architecture, and causal CockroachDB explanation above setup details |
| Access | Judge uses an isolated guest scenario; developer prerequisites are separate |
| Configure | One `.env.example`, grouped by credential scope |
| First use | One reset/run path creates the deterministic scenario |
| Debug | `doctor`, `status`, trace IDs, structured errors, and redacted logs identify the failing dependency |
| Deploy | Separate ECS/IAM/network/secrets/RLS guide |
| Upgrade | Forward-only migration, compatibility test, and stated rollback limits |
| Recover | Scenario reset, worker interruption drill, lease recovery, and clean shutdown |

## Developer empathy

I should not have to infer which of Docker, migrations, web, API, workers, Bedrock, SQL, and MCP failed. The command should tell me the failing boundary, why it matters, and the next action without showing a secret. I should be able to rerun one isolated synthetic scenario without touching another developer’s data.

## DX scorecard

| Dimension | Before | Target |
|---|---:|---:|
| Getting started | 5/10 | 9/10 |
| Command naming | 6/10 | 9/10 |
| Error help | 6/10 | 9/10 |
| Documentation | 7/10 | 9/10 |
| Configuration safety | 6/10 | 9/10 |
| Debuggability | 6/10 | 9/10 |
| Upgrade path | 5/10 | 8/10 |
| Evaluator path | 6/10 | 9/10 |

## DX implementation checklist

- one cross-platform command vocabulary;
- `/health` versus `/ready` contract;
- scoped credential groups and redacted doctor output;
- safe scenario-only reset;
- Windows and Linux clean-machine tests;
- trace-linked logs and errors;
- hosted verification command with optional real MCP check;
- forward-only migration and recovery guidance.
