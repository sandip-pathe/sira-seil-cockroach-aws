# SIRA + SEIL on AWS

This stack is the deployable production boundary for the qualified marketplace.
It deliberately keeps CockroachDB as the sole authority for missions, pinned
evidence, attempts, decisions, consent, and introductions.

## Runtime topology

- Vercel remains the only frontend host. Its same-origin API rewrite points to the
  AWS backend URL so browser cookies stay on the product domain.
- CloudFront is the backend HTTPS edge. Caching is disabled and viewer cookies,
  headers, and query strings reach the API.
- An internal Application Load Balancer sends all backend traffic to FastAPI.
- API, outbox dispatcher, qualification worker, and changefeed worker are separate
  private Fargate services with read-only roots and writable ephemeral mounts only where needed.
- The dispatcher publishes `QUALIFICATION_MISSION_READY` outbox rows to SQS FIFO.
  The qualification worker verifies the body digest, deduplicates in CockroachDB,
  invokes Bedrock and CockroachDB DVI, commits the fenced result, and only then
  acknowledges SQS.
- A versioned Bedrock Guardrail blocks prompt attacks and authority-bypass
  instructions and anonymizes direct contact, credential, and payment identifiers.
- The Guardrail also references an immutable Automated Reasoning policy for bilateral
  introduction and human purchase-authority claims. Its findings are explanatory-only:
  application policy, CockroachDB constraints and explicit human actions remain authority.
  The runtime verifies non-zero Automated Reasoning usage and never persists raw review text.
- Separate ARM64 AgentCore Runtimes execute SIRA and SEIL typed cognitive decisions under
  distinct principal locks, runtime audiences, IAM identities, prompt/tool bundles, and budgets.
  They are stateless, IAM-invoked, have no CockroachDB credential, and provision no AgentCore
  Memory. Every invocation requires a short-lived signed ticket bound to organization, actor,
  principal, party, purpose, audience, tools, and expiry. The trusted API persists validated,
  content-hashed results in CockroachDB. SIRA also retains the bounded synthetic experiment
  contract; SEIL cannot invoke it.
- An optional dedicated HTTP API and ARM64 Lambda accept authenticated CockroachDB
  changefeed webhooks and forward deterministic hints to an isolated SQS FIFO queue and
  DLQ. The bridge assumes at-least-once delivery and per-key ordering only; it drops source
  row data. A separate private worker re-reads every durable buyer tenant in CockroachDB,
  invalidates current decisions pinned to the changed product, and schedules one replacement
  through the ordinary outbox. It never sends hints to the qualification consumer directly.
- S3 stores versioned, checksum-addressed evidence bytes. CockroachDB stores the
  authoritative object identity and business relationship.
- Secrets Manager injects separate API, worker, and catalog SQL identities. The
  task definitions and CloudFormation template contain no database passwords.
- The API issues an HttpOnly, Secure, signed guest-session cookie and derives an isolated
  CockroachDB organization per browser. Firebase remains an optional account-upgrade
  path rather than a hidden deployment prerequisite.

The two-AZ VPC uses one NAT gateway to balance availability with hackathon cost.
The ALB and tasks have no public address. CloudWatch includes retained logs, a
dashboard, queue-age and 5xx alarms, and a DLQ alarm.

## Provision and deploy

Prerequisites: an AWS CLI profile, a CockroachDB Cloud database named `sira`, and
an administrative CockroachDB connection URL. Do not place the URL in a committed file.

```powershell
$env:AWS_PROFILE = "sira-hackathon"
$env:AWS_REGION = "us-east-1"
$env:DATABASE_ADMIN_URL = "cockroachdb+psycopg://.../sira?sslmode=verify-full"

$account = aws sts get-caller-identity --query Account --output text --profile $env:AWS_PROFILE
pnpm --filter @sira/aws-infra exec cdk bootstrap "aws://$account/$env:AWS_REGION"
uv run python scripts/provision_cloud.py --stage hackathon --profile $env:AWS_PROFILE --region $env:AWS_REGION
uv run python scripts/deployment_preflight.py --stage hackathon --profile $env:AWS_PROFILE --region $env:AWS_REGION
pnpm --filter @sira/aws-infra deploy
```

`provision_cloud.py` applies the Alembic migrations, creates and grants three
least-privilege SQL users, seeds the demo organizations, and writes generated
credentials directly to `sira-hackathon/runtime` in Secrets Manager. It prints
only non-secret metadata.

The deployment preflight then fails before CDK creates billable application resources unless the
AWS caller/region is valid and the runtime secret contains five exact fields, three distinct SQL
roles targeting one remote TLS-verified application database, and two distinct 32-byte signing
keys. All three runtime URLs must use the CockroachDB SQLAlchemy scheme; neither the API catalog
pool nor either worker mode can silently start against PostgreSQL in production. Its ignored report
contains hashes and booleans only.

After deployment, use the `BackendUrl` stack output as the target of the Vercel
same-origin rewrite. The default CloudFront domain is HTTPS-capable.

Configure these Vercel variables for Production and Preview, then rebuild the web app:

```text
SIRA_API_BASE_URL=<BackendUrl>
NEXT_PUBLIC_WEB_DATA_MODE=api
NEXT_PUBLIC_FIREBASE_API_KEY=<Firebase web config>
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=<Firebase web config>
NEXT_PUBLIC_FIREBASE_PROJECT_ID=<Firebase web config>
NEXT_PUBLIC_FIREBASE_APP_ID=<Firebase web config>
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=<Firebase web config>
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=<Firebase web config>
NEXT_PUBLIC_GUEST_SESSION_ENABLED=false
```

The browser calls relative `/v1/*` URLs and Vercel rewrites them to AWS, so no permissive
CORS middleware is required. CDK sets `WEB_BASE_URL` to the canonical Vercel production origin and rejects state-changing
requests whose `Origin` is not the configured Vercel origin. `FIREBASE_PROJECT_ID` is also
passed to the API so Firebase bearer tokens are verified server-side; Firebase web config
values never grant backend authority by themselves.

The first local deployment also creates `GithubDeployRoleArn`. Set these public
repository variables before using the manual `Deploy AWS` workflow:

```text
AWS_ACCOUNT_ID=<account number>
AWS_REGION=us-east-1
AWS_DEPLOY_ROLE_ARN=<GithubDeployRoleArn output>
FIREBASE_PROJECT_ID=<Firebase project ID>
```

The role trusts only `sandip-pathe/sira-seil-cockroach-aws` on `main` and can
only assume this account and region's standard CDK bootstrap roles. GitHub uses
short-lived OIDC credentials; no AWS access key is stored in repository secrets.
The workflow remains manual and verifies the infrastructure package before deploy.

## Verification

```powershell
pnpm --filter @sira/aws-infra build
pnpm --filter @sira/aws-infra test
pnpm --filter @sira/aws-infra synth
docker build --file Dockerfile --tag sira-api:local .
docker build --file Dockerfile.web --tag sira-web:local .
docker buildx build --platform linux/arm64 --file Dockerfile.agentcore --tag sira-agentcore:local .
```

Deployment is not proven until `/health` reports `database=\"configured\"`, an
actual conversation/mission travels through SQS or the signed runtime boundary and Bedrock to a current Cockroach decision,
the consumer receipt exists, the queue drains, and the integrity page verifies
the same decision and pinned evidence hashes.

The committed Automated Reasoning definition follows AWS's CloudFormation format, but must
still be exercised against labelled valid, invalid, ambiguous and untranslated cases after
deployment. A synthesized policy is not evidence that Bedrock translated those cases correctly.

After the core hosted path is green, configure the optional changefeed with the
`ChangefeedWebhookUrl` output and the generated secret referenced by
`ChangefeedWebhookTokenSecretName`. Supply the value through CockroachDB's
`webhook_auth_header` option as `Basic <secret>`; never place it in repository files.
Use JSON with `updated`, `topic_in_value`, and `key_in_value`. Delivery is not exactly once:
the Lambda's stable source hash is a FIFO optimization, while durable correctness still comes
from re-reading CockroachDB and consumer/effect uniqueness constraints. The committed stack
retains these hints in `ChangefeedHintQueueUrl`; the state-reread consumer cannot interfere with
the qualification work queue. Create the changefeed only
for `qualification_active_product_bundles`: inserting an immutable candidate bundle is not a
business-state change; advancing that active pointer is the authoritative activation event.
