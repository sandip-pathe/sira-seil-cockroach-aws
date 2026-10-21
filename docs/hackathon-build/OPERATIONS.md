# Operations

## Local development

Set `OPENAI_API_KEY` in `.env`, then use:

```powershell
uv run sira-dev up --profile local
uv run sira-dev status
uv run sira-dev logs
uv run sira-dev check
uv run sira-dev down
```

The local profile starts CockroachDB, applies migrations and grants, then starts the API, Python qualification worker, and web app. The product marketplace starts empty and stores public observations as SIRA discovers products. The worker reads the durable outbox directly from CockroachDB.

## Recovery contract

- Worker interruption: a replacement worker claims work after lease expiry with a higher fencing generation. A stale worker cannot checkpoint or finalize.
- Duplicate work: CockroachDB consumer receipts and effect keys make reprocessing idempotent.
- Evidence changes during evaluation: finalization detects stale inputs, rejects the attempt, and schedules a bounded replacement.
- Model/API interruption: LangGraph retries transient provider failures. Unfinished work remains represented in CockroachDB and can be claimed again.

## Database checks

```powershell
uv run python scripts/cockroach_security_audit.py
uv run python scripts/cockroach_restore_drill.py
uv run python scripts/cockroach_upgrade_drill.py
```

These checks require the documented local database setup and credentials. The restore and upgrade drills use disposable databases.

## Hosting readiness

The app has not been deployed. Before choosing a host, provide persistent evidence-object storage, configure CockroachDB connectivity and tenant roles, set OpenAI and identity secrets, and verify HTTPS and backup/restore procedures. OpenAI does not host the app or its database/files.
