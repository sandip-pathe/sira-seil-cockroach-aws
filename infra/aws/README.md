# SIRA + SEIL on AWS

This stack is the deployable production boundary for the qualified marketplace.
It deliberately keeps CockroachDB as the sole authority for missions, pinned
evidence, attempts, decisions, consent, and introductions.

## Runtime topology

- CloudFront is the public HTTPS edge. Caching is disabled for authenticated and
  transactional routes, and viewer cookies, headers, and query strings reach the app.
- An internal Application Load Balancer routes `/v1/*` and `/health` to FastAPI;
  all other paths go to the standalone Next.js service.
- API, web, outbox dispatcher, and qualification worker are separate private
  Fargate services with read-only roots and writable ephemeral mounts only where needed.
- The dispatcher publishes `QUALIFICATION_MISSION_READY` outbox rows to SQS FIFO.
  The qualification worker verifies the body digest, deduplicates in CockroachDB,
  invokes Bedrock and CockroachDB DVI, commits the fenced result, and only then
  acknowledges SQS.
- A versioned Bedrock Guardrail blocks prompt attacks and authority-bypass
  instructions and anonymizes direct contact, credential, and payment identifiers.
- S3 stores versioned, checksum-addressed evidence bytes. CockroachDB stores the
  authoritative object identity and business relationship.
- Secrets Manager injects separate API, worker, and catalog SQL identities. The
  task definitions and CloudFormation template contain no database passwords.

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
pnpm --filter @sira/aws-infra deploy
```

`provision_cloud.py` applies the Alembic migrations, creates and grants three
least-privilege SQL users, seeds the demo organizations, and writes generated
credentials directly to `sira-hackathon/runtime` in Secrets Manager. It prints
only non-secret metadata.

After deployment, use the `ApplicationUrl` stack output. A custom domain can be
added later with a CloudFront ACM certificate in `us-east-1`; the default
CloudFront domain is already HTTPS-capable.

## Verification

```powershell
pnpm --filter @sira/aws-infra build
pnpm --filter @sira/aws-infra test
pnpm --filter @sira/aws-infra synth
docker build --file Dockerfile --tag sira-api:local .
docker build --file Dockerfile.web --tag sira-web:local .
```

Deployment is not proven until `/health` reports `database=\"configured\"`, an
actual mission travels through SQS and Bedrock to a current Cockroach decision,
the consumer receipt exists, the queue drains, and the integrity page verifies
the same decision and pinned evidence hashes.
