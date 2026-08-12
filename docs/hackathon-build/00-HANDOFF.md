# SIRA + SEIL - CockroachDB x AWS build handoff

Status: active implementation

Date: 2026-08-13

Canonical repository: `https://github.com/sandip-pathe/sira-seil-cockroach-aws` (private during construction)

Current implementation commit: `f8db5e8`

## Product lock

SIRA helps a company choose what software to buy. SEIL makes seller and public product evidence comparable. CockroachDB keeps their concurrent work correct, durable, and independently inspectable.

Do not rename the product around memory. Do not build a separate proof/infrastructure product. Keep PRAVA optional and human-approved.

## Completed

- Original Git history restored and the current hackathon boundary tagged.
- Canonical repository created and pushed.
- Abandoned nested side build deleted.
- DataHub, Senso, Snowflake, Temporal, PRAVA MCP/OAuth, old PostgreSQL runtime/migrations, and old submission surfaces removed from the active tree.
- Web checks, generated client, and Python lint pass on cleanup commit `f8db5e8`.

## Current truth

The root product has no CockroachDB implementation yet. It is intentionally between persistence runtimes after cleanup. Deleted side-repository tests do not count.

Next: add the root CockroachDB compatibility slice, then the minimal schema, Bedrock/vector retrieval, concurrency/recovery protocol, product integration, AWS hosting, and real Cloud MCP proof. `checklist.md` is authoritative.

## Required live claim

1. SIRA snapshots seller pack v1 (`EU hosting available`).
2. SEIL publishes v2 (`US-only`) during evaluation.
3. The stale v1 attempt is invalidated and emits no decision.
4. One replacement uses v2 and blocks the lower-cost option.
5. A standby worker resumes durable work after interruption.
6. Duplicate delivery creates one effect and one decision.
7. Bedrock and Cockroach vector retrieval are real.
8. A scoped Cloud MCP session independently passes five integrity checks over that same mission.

## Read order

1. `checklist.md` - current execution contract.
2. `plan.md` - current status, architecture, and remaining order.
3. `prd.md` - product behavior.
4. `spec.md` - technical invariants.
5. `test-plan.md` - proof contract.
6. `provenance.md` - reuse disclosure.

## Resume instruction

> Continue the SIRA + SEIL CockroachDB x AWS build in the root repository. Read `docs/hackathon-build/00-HANDOFF.md`, `checklist.md`, and `plan.md`. Work autonomously from the first unchecked task, use focused commits, push only the intended paths, and never count deleted side-repository work as evidence.
