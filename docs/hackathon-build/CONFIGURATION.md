# Configuration contract

## Credential groups

| Group | Used by | Examples | Rule |
|---|---|---|---|
| Browser-public | Web client | Firebase public project settings, public API base URL | Explicitly marked public; never includes signing/admin material |
| Runtime SQL | API and workers | `DATABASE_URL` | Least-privilege application role; runtime only |
| Migration/admin | Migration job | `DATABASE_ADMIN_URL` | Never reaches API, workers, browser, or logs |
| AWS runtime | ECS task roles | region, Bedrock model ID | Prefer task roles; do not request long-lived AWS keys in `.env` |
| MCP operator | External MCP client | cluster scope, OAuth/service-account configuration | Lives in the operator client, not the public application |
| Demo | Hosted API | demo account and scenario flag | Allows only isolated synthetic scenario controls |

`.env.example` contains variable names, comments, and safe defaults only. It contains no keys, tokens, certificate bodies, connection strings, or real project IDs.

## Required logical settings

```text
DATABASE_URL
DATABASE_ADMIN_URL                 # migration process only
AWS_REGION
BEDROCK_EMBEDDING_MODEL=amazon.titan-embed-text-v2:0
BEDROCK_EMBEDDING_DIMENSION=1024
SIRA_HOSTED_MODE=true|false
SIRA_FIXTURE_FALLBACK=false        # required when hosted
SIRA_DEMO_MODE=true|false
SIRA_DEMO_ORGANIZATION_ID          # synthetic tenant only
PUBLIC_API_BASE_URL
FIREBASE_*                         # public browser values only where applicable
```

MCP configuration is intentionally absent from the app environment unless an implemented server-side feature truly calls MCP. The default design keeps it in the external operator client.

## Doctor contract

`uv run sira-dev doctor --profile <profile>` reports only `READY`, `MISSING`, `INVALID`, or `SKIPPED`:

```text
CockroachDB SQL       READY   cluster and database matched
Schema                READY   expected migration head
Runtime role          READY   tenant policies enforced
Public catalog        READY   buyer-readable projection exists
Vector indexes        READY   context and catalog indexes found
Bedrock embeddings    READY   model and 1024 dimensions matched
Workers               READY   2 active
MCP operator scope    READY   demo cluster, configured read-only
Fixture fallback      OFF     hosted-safe
```

Cluster-scoped MCP configuration does not itself prove tenant isolation. SQL/RLS and API tests prove tenant boundaries separately.

## Health endpoints

- `/health` — process is alive and configuration parsed; no dependency secrets or private data.
- `/ready` — required CockroachDB schema/role checks and Bedrock configuration are usable. External MCP is reported separately because it does not control recommendations.

Unavailable CockroachDB means `/ready` is not ready. The app never falls back to a fixture result.
