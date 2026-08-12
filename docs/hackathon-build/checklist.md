# Build checklist

Status: Approach B approved; execution reset to the reviewed architecture on 2026-08-13.

## Working rules

- Work only in `D:\s\siel-n-sira` and create focused local commits.
- Preserve unrelated user changes; stage named paths only.
- A checked item requires its stated evidence. Unavailable credentials leave the item open; hosted mode never substitutes fixtures.
- P0 gates precede P1/P2. The correctness kernel cannot be cut.

## P0

- [x] **0. Preserve history, canonical repository and sponsor cleanup**
  Build: retain original August history and `cockroachdb-hackathon-start`; use the canonical repository; remove obsolete DataHub/Senso/Snowflake/Temporal and old PostgreSQL runtime surfaces.
  Accept: original source is an ancestor; boundary tag and canonical remote exist; cleanup commit remains in history.
  Verify: `git show cockroachdb-hackathon-start`; `git remote -v`; `git log --oneline --decorate -10`.

- [x] **1. Approve the qualified-agent-marketplace architecture**
  Build: lock the product outcome, authority model, Product Bundle dependency contract, Cockroach/AWS topology, P0 routes, cut lines and P1/P2 boundary.
  Accept: `architecture.md` and `plan.md` agree; reviewed Office Hours design is approved; no “memory” rebrand or decorative service requirement remains.
  Verify: document link/UTF-8 checks and manual architecture review.

- [ ] **2. Pass cloud and compatibility preflight**
  Build: validate clean repository baseline, AWS caller identity/region and spend ceiling; prove Cockroach TLS SQL, fresh-session `40001` retry, pooled FORCE RLS, `VECTOR(1024)`/DVI `EXPLAIN`, Managed MCP read-only view and backup status; prove Bedrock Converse tool use, Guardrail intervention and Titan V2 1,024-dimensional output.
  Accept: each gate has a sanitized `artifacts/preflight/*.json`; no secrets are recorded; failed DVI/MCP blocks the architecture rather than being replaced.
  Verify: `pytest tests/cockroach_integration/test_compatibility.py -q`; provider smoke commands documented in the artifact.

- [ ] **3. Implement the Cockroach transaction and tenant foundation**
  Build: Cockroach configuration/dialect, whole-callback retry runner, transaction-local verified tenant/principal/role context, pool sanitation, runtime-role readiness and migration runner.
  Accept: no model/network call occurs inside retry callbacks; missing tenant context denies access; one reused physical connection cannot leak tenants; retries use fresh sessions and bounded jitter.
  Verify: unit tests plus real Cockroach retry/RLS/pool integration tests.

- [ ] **4. Implement the authoritative P0 schema**
  Build: immutable buyer-context/brief/evidence/Product Twin/catalog/Product Bundle versions; embeddings; missions, attempts, input/dependencies, checkpoints; decisions/citations; engagements/responses/consents/introductions; idempotency, events, outbox, consumer receipts and effects.
  Accept: active Product Bundle activation is atomic; published business inputs are insert-only for application roles; all tenant FKs are scoped; unique constraints enforce one direct successor, current decision, consent/digest, consumer receipt and semantic effect.
  Verify: fresh migration, schema assertions, immutable-write negatives, RLS/grant audit and migration smoke.

- [ ] **5. Prove the correctness kernel on real CockroachDB**
  Build: database-time claim/lease/generation, committed snapshot, controlled barrier, checkpoint, stale finalization, one direct replacement, bounded chain, lease takeover, durable duplicate suppression and atomic qualified introduction.
  Accept: v1 emits no result after v2 activation; one replacement cites v2; old generation cannot write; repeated outbox/finalization/effect calls leave counts at one; `40001` exhaustion is visible.
  Verify: deterministic barrier, concurrent finalizer, worker-kill/takeover and duplicate-delivery integration tests.

- [ ] **6. Implement DVI and Bedrock agent quality**
  Build: separate private buyer and buyer-safe Product Bundle vector spaces; Titan V2 metadata; resumable corpus loader; typed Bedrock Converse runtime/tools; Guardrails; budgets; deterministic replay and labelled evaluation set.
  Accept: semantic query finds the expected candidate; relational gates exclude stale/private/ineligible rows; citations are bundle subsets; hard-gate/tool/schema/leakage tests are 100%; fit classification and groundedness meet `architecture.md` thresholds.
  Verify: vector query plan/candidate artifact, live provider smoke, deterministic agent suite and committed evaluation report.

- [ ] **7. Implement SQS/S3/observability adapters**
  Build: preseed checksum-verified S3 evidence; Cockroach outbox dispatcher to SQS FIFO; role-configured consumer; durable receipt; bounded retry/DLQ policy; sanitized correlation logs and P0 metrics.
  Accept: dispatcher crash/redelivery is harmless beyond FIFO's dedup window; message deletion follows result commit; secrets/private prompts are absent from logs.
  Verify: adapter contract tests, duplicate/redrive integration test, IAM policy assertions and log scan.

- [ ] **8. Implement P0 API and fail-closed composition**
  Build: briefs, missions/events, v2 bundle publication, engagement/response, decision approval/rejection, consent/introduction and integrity endpoints with auth-derived parties, idempotency and ETags.
  Accept: OpenAPI matches implementation; hosted dependencies reject missing Cockroach/AWS/auth configuration; stable errors include problem/cause/recovery/trace; no fixture winner appears.
  Verify: API contract/auth/idempotency/conflict tests and OpenAPI/client generation checks.

- [ ] **9. Implement the six P0 UI routes**
  Build: `/sira`, `/sira/missions/[id]`, `/seil/products/[id]/evidence`, `/seil/opportunities/[id]`, `/matches/[id]`, `/integrity/[missionId]` over live APIs.
  Accept: each route has loading/empty/partial/error/conflict/stale/success states; controlled race is understandable without console access; keyboard/mobile/WCAG checks pass; no broad unrelated component rewrite.
  Verify: web lint/type/build, browser E2E, accessibility/responsive checks and full local Cockroach journey.

- [ ] **10. Deploy the isolated hackathon-demo stack on AWS**
  Build: minimal CDK/ECR/ALB/ECS/SQS/S3/IAM/Secrets/CloudWatch; separate web/API/worker images; production configuration omits the demo controller module/route/permission.
  Accept: public HTTPS flow works without local services; task roles are least-privilege; secrets remain server-only; deployment/rollback and health/readiness work.
  Verify: CDK synth/assertions, image scan, hosted smoke, task-role review and redacted traces.

- [ ] **11. Prove Managed MCP integrity and freeze evidence**
  Build: sanitized read-only views for current dependencies, attempts/fences/replacements, effect counts and DVI plan inputs; run MCP from a separate scoped identity.
  Accept: MCP verifies the same mission/decision IDs shown in UI; five consecutive hosted rehearsals yield identical invariant counts; scorecard claims match evidence.
  Verify: MCP transcript/manifest pinned to commit, demo runbook, repository/license/disclosure/secret scan and manual rubric audit.

## P1 after every P0 gate

- [ ] Buyer company-memory editing and decision history/inbox.
- [ ] Seller product portfolio, opportunity inbox and interactive versioned S3 ingestion.
- [ ] Public marketplace/product pages backed by published Product Bundles and DVI.
- [ ] Settings/disclosure management, complete DLQ/replay operations, restore drill and broader telemetry.
- [ ] `ccloud` provision/doctor/backup/restore evidence and GitHub Actions OIDC delivery.

## P2 after P1 or when independently safe

- [ ] Human-approved PRAVA introduction-to-payment adapter with provider reconciliation.
- [ ] Bedrock Automated Reasoning as an explanatory policy check, never authority.
- [ ] AgentCore Runtime/evaluation experiment without AgentCore Memory.
- [ ] Measured Cockroach changefeed, multi-region and regional-survival experiments.
- [ ] Analytics, additional categories and outcome-learning surfaces backed by real events.
