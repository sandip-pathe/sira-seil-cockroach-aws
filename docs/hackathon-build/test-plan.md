# Verification plan

## Local contracts

```powershell
uv run ruff check python services tests scripts
uv run ruff format --check python services tests scripts
uv run mypy python services
uv run pytest -m "not cockroach and not provider"
uv run python scripts/generate_openapi.py --check
uv run python scripts/evaluate_qualification_agent.py --check
```

## CockroachDB integration

Start the local CockroachDB service, apply migrations and role grants, then run:

```powershell
uv run pytest tests/cockroach_integration -m cockroach
uv run python scripts/cockroach_security_audit.py
uv run python scripts/cockroach_restore_drill.py
uv run python scripts/cockroach_upgrade_drill.py
```

These checks cover tenant isolation, vector retrieval, concurrent version changes, leases, idempotency, and schema recovery.

## Web

```powershell
pnpm check:web
pnpm test:browser
```

Live provider checks require `OPENAI_API_KEY`.
