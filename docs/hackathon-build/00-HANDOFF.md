# SIRA + SEIL - CockroachDB x AWS build handoff

Status: R1 local core implemented; R2 live cloud verification pending

Date: 2026-08-18

Canonical repository: `https://github.com/sandip-pathe/sira-seil-cockroach-aws` (private during construction)

Current implementation is the local `main` history. Use `git log -1 --oneline` rather than a
hard-coded commit because focused local commits continue until the cloud gate.

## Product lock

SIRA helps a company choose what software to buy. SEIL makes seller and public product evidence comparable. CockroachDB keeps their concurrent work correct, durable, and independently inspectable.

Do not rename the product around memory. Do not build a separate proof/infrastructure product. Keep payment external and human-approved.

## Completed

- Original Git history restored and the current hackathon boundary tagged.
- Canonical repository created and pushed.
- Abandoned nested side build deleted.
- DataHub, Senso, Snowflake, Temporal, legacy payment integrations, old PostgreSQL runtime/migrations, and old submission surfaces removed from the active tree.
- Web checks, generated client, and Python lint pass on cleanup commit `f8db5e8`.

## Current truth

Approach B was approved on 2026-08-13 and narrowed by the flagship review. The current source of
truth is `../flagship-platform-plan.md`; this directory retains the CockroachDB x AWS evidence
gates and submission material.

The local correctness kernel, typed cognitive runtime, bilateral exchange, isolated guest path,
and two-runtime CDK topology are implemented. Cloud/compatibility evidence remains open. Deleted
side-repository work, targets, generated assets, or deterministic fixtures do not count as live
provider evidence.

## Required live claim

1. SIRA snapshots the active v1 Product Bundle (`EU hosting available`).
2. SEIL atomically activates the v2 Product Bundle (`US-only`) after `SNAPSHOT_COMPLETE`.
3. The stale v1 attempt is invalidated and emits no decision.
4. One direct replacement uses v2 and blocks the lower-cost option.
5. A standby worker resumes durable work after interruption.
6. Duplicate delivery creates one effect and one decision.
7. Bedrock and Cockroach vector retrieval are real.
8. A scoped Cloud MCP session independently passes five integrity checks over that same mission.

## Read order

1. `architecture.md` - approved product, data, agent, AWS and Cockroach contract.
2. `checklist.md` - evidence-gated P0/P1/P2 execution contract.
3. `plan.md` - implementation order and cut lines.
4. `prd.md` - product behavior.
5. `spec.md` - technical invariants; update when implementation changes a contract.
6. `test-plan.md` - proof contract.
7. `provenance.md` - reuse disclosure.

## Resume instruction

> Continue the SIRA + SEIL CockroachDB x AWS build in the root repository. Read `docs/hackathon-build/architecture.md`, `00-HANDOFF.md`, `checklist.md`, and `plan.md`. Work autonomously from the first unchecked task, use focused commits, and never count targets, fixtures, or deleted side-repository work as evidence.
