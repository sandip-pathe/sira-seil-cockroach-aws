# Operations and recovery contract

Status: core runtime and safe DLQ controls are implemented; hosted drills remain pending.

## Cockroach Cloud preflight

Run the credential-safe cluster, managed-backup, and restore-readiness check with:

```powershell
uv run python scripts/cockroach_cloud_doctor.py --cluster <cluster-name>
```

It writes only booleans, counts, a hashed cluster name, and hashes of CLI output to
`.artifacts/preflight/cockroach-cloud.json`; it never persists connection details or raw CLI output.
It fails closed when `ccloud` is unavailable or unauthenticated, the cluster is not a created AWS
cluster, backups are disabled or absent, restore history is inaccessible, or the installed CLI does
not expose the documented backup and restore commands. Authenticate interactively with
`ccloud auth login` before collecting judging evidence.

## Bedrock provider preflight

Run the live Converse and Titan Text Embeddings V2 contract smoke with an authenticated AWS
profile:

```powershell
uv run python scripts/aws-bedrock-smoke.py --region us-east-1 --profile sira-hackathon
uv run python scripts/evaluate_bedrock_qualification.py --region us-east-1 --profile sira-hackathon
```

The commands write `.artifacts/preflight/bedrock.json` and
`.artifacts/preflight/bedrock-quality.json`. The latter runs five synthetic labelled cases through
the production-style inspect-every-candidate tool loop, typed output and grounding validator. Both
artifacts exclude credentials, raw prompts, raw evidence and raw model output. Guardrail
intervention remains a separate deployment gate and is stated as such in the artifacts.

## Browser accessibility and responsive smoke

Build and start the web application, then run the installed-Chrome suite:

```powershell
pnpm build:web
pnpm --filter @sira/web start --hostname 127.0.0.1 --port 3000
pnpm test:browser
```

The suite checks every P0 route at desktop and mobile widths for server failures, horizontal
overflow and WCAG A/AA violations, plus the keyboard contract of the available setup or
navigation state. It uses the locally installed Chrome channel and writes failure-only traces and
screenshots beneath ignored `.artifacts/playwright`. A pass against a fail-closed authentication
setup state does not replace the separate hosted authenticated-journey gate.

## CockroachDB security and immutability audit

Run the audit through an administrative connection that is available only to the migration job:

```powershell
uv run python scripts/cockroach_security_audit.py
```

The audit checks every tenant table for enabled and forced RLS, at least one policy, and an owner
distinct from `sira_runtime`. It additionally proves that immutable version/dependency/citation
tables grant only `SELECT` and `INSERT`, never `UPDATE`, `DELETE`, or `TRUNCATE`. The persisted
artifact contains counts, violations, and a schema fingerprint—not table owners, raw grants, or
connection data.

## Disposable local restore drill

Run a real CockroachDB backup and restore into a uniquely named temporary database:

```powershell
uv run python scripts/cockroach_restore_drill.py
```

The verifier refuses system or unsafe source database names, snapshots only bounded counts and
the Alembic head, runs `BACKUP` and `RESTORE ... WITH new_db_name`, compares a sanitized digest,
and drops the temporary database in `finally`. Its ignored artifact is
`.artifacts/preflight/cockroach-restore.json`; it contains no row payloads, SQL URL, usernames or
temporary database name. This proves the local restore procedure. Cockroach Cloud managed backup
and restore evidence remains a separate hosted gate.

## Normal commands

```text
uv run sira-dev status
uv run sira-dev logs --trace <trace-id>
uv run sira-demo verify --latest
uv run sira-demo verify --base-url https://<app> --scenario evidence-race --mcp
```

Every scenario run prints its scenario ID, mission ID, trace ID, public URL, current step, and next action. Logs are structured and redacted.

## Isolated reset

`sira-demo reset` requires an explicit scenario and the authorized synthetic demo organization. It refuses a missing, wildcard, production, or non-demo tenant. It deletes/reseeds only that scenario’s synthetic rows.

It never resets a shared database, another tenant, or a cloud cluster.

## Recovery drills

### Worker interruption

1. Confirm two workers are active.
2. Pause after a durable checkpoint.
3. Stop the active worker.
4. Observe lease expiry using database time.
5. Confirm the standby claims a larger fencing token and resumes.
6. Confirm the old worker cannot checkpoint or finalize.

### Evidence race

1. Reset the synthetic scenario.
2. Capture seller pack v1.
3. Publish v2 while evaluation is outside a transaction.
4. Confirm the v1 attempt becomes invalidated with no decision.
5. Confirm one replacement attempt uses v2 and one final decision exists.

### Duplicate delivery

Replay the same demo event ten times. The database returns the existing result or a safe no-op. One effect and one mission decision exist.

### Qualification DLQ

The operator command reads queue counts and native message-move-task state. It never receives message bodies. Mutating commands are dry-run unless `--execute` is present.

```powershell
uv run python scripts/qualification_dlq.py --region us-east-1 --profile sira-hackathon --dlq-url <QualificationDlqUrl> status
uv run python scripts/qualification_dlq.py --region us-east-1 --profile sira-hackathon --dlq-url <QualificationDlqUrl> start --max-rate 10
uv run python scripts/qualification_dlq.py --region us-east-1 --profile sira-hackathon --dlq-url <QualificationDlqUrl> start --max-rate 10 --execute
uv run python scripts/qualification_dlq.py --region us-east-1 --profile sira-hackathon --dlq-url <QualificationDlqUrl> cancel --task-handle <handle> --execute
```

Before redrive, diagnose and fix the underlying failure, confirm the worker build and schema head, record the visible-message count, and begin at a bounded rate. Cockroach consumer receipts and effect keys remain the duplicate-delivery authority; SQS redrive is transport recovery, not business-state repair.

## Failure help

| Failure | Message | Operator action |
|---|---|---|
| CockroachDB unavailable | `Decision state is unavailable. No recommendation was created.` | Check `/ready`, network, certificate, and `DATABASE_URL` |
| Schema mismatch | `Database schema does not match this build.` | Run the documented migration job with admin credentials |
| Bedrock denied/throttled | `Evidence search is delayed. The mission is saved and can be retried.` | Check task role, region, and model access |
| Version conflict | `Evidence changed while SIRA was checking it. Restarting with version 2.` | Normal transition; verify replacement attempt |
| Lease loss | `This worker stopped. Another worker is continuing from the saved checkpoint.` | Confirm new fencing token; old worker stops |
| Stale vector | `Some evidence changed and is being refreshed. It will not be used yet.` | Re-embed; require enough current evidence |
| MCP auth/scope | `The independent integrity check could not reach the scoped demo cluster.` | Fix external client scope; recommendation remains unchanged |
| Integrity mismatch | `Integrity check failed: <invariant>.` | Stop submission claim and inspect the named attempt |

## Upgrade rule

- forward-only production migration by default;
- test upgrade from the prior supported migration head on a disposable database;
- document whether rollback is data-safe before offering it;
- never run the imported PostgreSQL Alembic chain directly on CockroachDB;
- stop deployment when compatibility checks or role/policy checks fail.
