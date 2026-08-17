# Provenance and reuse ledger

This repository preserves real history and distinguishes reused SIRA/SEIL product work from current hackathon work.

## Source history

| Item | Value |
|---|---|
| Original upstream | `https://github.com/uruja/siel-n-sira` |
| Original branch | `core-backend` |
| Imported commit | `8d917eba039b59b2c1a0f35d832093806101260c` |
| Original project period | August 2026 prior hackathon work |
| Current canonical repository | `https://github.com/sandip-pathe/sira-seil-cockroach-aws` |
| Current hackathon boundary | tag `cockroachdb-hackathon-start` at `b6f98554c8c43407d3f9bb672bd2c2d5712614aa` |
| Active cleanup commit | `f8db5e8` |
| License | Apache-2.0 |

A repository name or new remote does not make reused code new. The commit graph and this ledger provide the disclosure boundary.

## Reused product foundation

- SIRA and SEIL routes and three-panel workspace.
- Buyer/seller product model and authority concepts.
- Firebase/auth boundary.
- Deterministic eligibility and ranking logic, subject to existing fixture drift.
- Seller evidence, research-only labeling, and narrow external payment-handoff concepts where they remain cleanly separable.

## Removed from active scope

- DataHub runtime, proof code, scripts, pages, screenshots, and submission artifacts.
- Senso adapters/configuration/tools.
- Snowflake integration, infrastructure, routes, and fixtures.
- Temporal runtime.
- Payment-provider MCP/OAuth.
- PostgreSQL Compose/bootstrap runtime and imported Alembic migration chain.
- Abandoned nested `cockroach-build` side repository.

All removed work remains visible in Git history; it is not part of the current product or current submission.

## New current-hackathon work

Do not describe an item as complete until its root-repository verification passes:

- CockroachDB local and Cloud schema/migrations;
- SQLSTATE `40001` whole-callback retry handling;
- RLS/session-scope compatibility and tenant tests;
- `VECTOR(1024)` context and catalog storage plus distributed indexes;
- Bedrock Titan Text Embeddings V2 integration and freshness checks;
- immutable decision-input snapshots and mixed-version invalidation;
- conditional leases, fencing, checkpoints, recovery, and duplicate suppression;
- real external CockroachDB Cloud Managed MCP integrity inspection;
- ECS/Fargate API and two-worker deployment;
- Cockroach-specific states in the existing SIRA/SEIL UI;
- hosted evidence bundle and submission assets.

## Build ledger

| Date | Commit | Change | Classification | Verification | Public claim |
|---|---|---|---|---|---|
| 2026-08-12 | planning only | Scope, PRD, spec, checklist, and reviews | New planning | Document review | Planned only |
| 2026-08-13 | history repair through `b6f9855` | Restored ancestry, boundary tags, canonical private remote | Repository/provenance work | ancestry, tags, bundle, push | Honest history established |
| 2026-08-13 | `f8db5e8` | Removed prior sponsor/runtime surfaces from active tree | New cleanup over reused product | web check, generated client, Python lint | Active product no longer depends on removed stack |

## Required Devpost disclosure

> SIRA and SEIL existed before this hackathon as buyer and seller software agents. For this event we removed the previous sponsor stack and built the CockroachDB state layer, distributed vector retrieval, concurrent version checks, worker recovery, Cloud MCP inspection, and AWS deployment that are actually demonstrated. The repository preserves the original history and records the new-work boundary.

Narrow that wording if the final build implements less. Never list optional or deleted work as current implementation.
