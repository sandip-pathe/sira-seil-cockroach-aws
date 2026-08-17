# Build checklist

Status: R1 local core implemented; R2 live cloud proof blocked on credentials/resources; R3
hardening remains. Current as of 2026-08-18.

## Working rules

- Work only in `D:\s\siel-n-sira` and create focused local commits.
- Preserve unrelated user changes; stage named paths only.
- A checked item requires its stated evidence. Unavailable credentials leave the item open; hosted mode never substitutes fixtures.
- P0 gates precede P1/P2. The correctness kernel cannot be cut.

## Evidence snapshot (2026-08-18)

- Official local gate: Ruff, format, Mypy over 120 source files, architecture boundaries,
  OpenAPI/client drift, web lint/type checks, CDK build/test/synth, and current-tree credential
  scan pass. The non-provider suite passes `436` tests. The live-Cockroach suite contains `112`
  executions across `13` integration categories and runs separately.
- Live local CockroachDB v26.2.3: fresh migration reaches `cdb0018`; DVI is present; `13`
  integration categories cover readiness/FORCE RLS/pool reuse, real `40001`, DVI/current bundles,
  stale replacement, lease/fencing, bilateral isolation and simultaneous offer races. The
  evidence-version race is permanently parameterized for `100` real-Cockroach executions and
  passes with zero stale decisions and exactly one direct replacement per execution. The
  `evidence-race` reset/run/verify scenario passes against CockroachDB, not SQLite.
- The same-browser guest path now receives a globally unique isolated fixture tenant and can open
  the buyer and seller projections of one opaque capability-scoped exchange. Production identities
  cannot use this development bridge.
- AWS package: CDK build, six topology/IAM/AgentCore/Automated-Reasoning/changefeed tests and synth
  pass. It defines distinct SIRA and SEIL AgentCore runtimes and endpoints with zero AgentCore Memory
  resources. Live deployment is not claimed.
- AWS provider: live Nova Converse and Titan V2 smoke passes in `us-east-1` with a normalized 1,024-dimensional embedding. A separate five-case live Nova qualification evaluation passes typed output, inspect-every-candidate, groundedness and expected-product gates at 100%; Guardrail intervention remains deployment-gated.
- A disposable local Cockroach backup/restore drill passes with matching schema/count digests and verified temporary-database cleanup. Cockroach Cloud managed backup/restore remains a separate external gate.
- A disposable forward-upgrade drill passes from `cdb0017` (`99` tables) to `cdb0018` (`100`
  tables), including the new handoff table, forced RLS, three runtime policies and verified cleanup.
- A sanitized local API timing gate passes: health p95 `2.26 ms`, Cockroach readiness p95
  `119.04 ms`, catalogue p95 `2.27 ms`, and a durable lightweight turn p95 `207.65 ms`. These are
  same-machine development measurements, not hosted-load claims.
- Not yet evidence: CockroachDB Cloud TLS/Managed MCP/managed backup, deployed AWS URL, provider
  evaluation on the current build, hosted rehearsals, hosted browser journey, distributed trace,
  live Guardrail intervention, load/chaos, or managed restore. The AWS CLI session expired during
  this pass and must be renewed before any live claim.

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

- [x] **3. Implement the Cockroach transaction and tenant foundation**
  Build: Cockroach configuration/dialect, whole-callback retry runner, transaction-local verified tenant context, server-validated principal/role capability, pool sanitation, runtime-role readiness and migration runner.
  Accept: no model/network call occurs inside retry callbacks; missing tenant context denies access; one reused physical connection cannot leak tenants; retries use fresh sessions and bounded jitter.
  Verify: `tests/unit/test_cockroach_database.py`, `tests/unit/test_database_readiness.py`, and both live `tests/cockroach_integration/test_foundation.py` tests pass. The SQL credential is network-private/non-owner/non-admin without `BYPASSRLS`; browser clients never receive it.

- [ ] **4. Implement the authoritative P0 schema**
  Build: immutable buyer-context/brief/evidence/Product Twin/catalog/Product Bundle versions; embeddings; missions, attempts, input/dependencies, checkpoints; decisions/citations; engagements/responses/consents/introductions; idempotency, events, outbox, consumer receipts and effects.
  Accept: active Product Bundle activation is atomic; published business inputs are insert-only for application roles; all tenant FKs are scoped; unique constraints enforce one direct successor, current decision, consent/digest, consumer receipt and semantic effect.
  Verify: fresh migration, schema assertions, immutable-write negatives, RLS/grant audit and migration smoke.
  Progress: migrations through `cdb0018`, tenant FKs/constraints, Product Bundles, embeddings,
  cognitive journals/runtime replay, bilateral commands/projections/evidence/offers/handoffs,
  missions/attempts/decisions/engagements/receipts/effects, versioned company context/workspace
  settings and immutable object identity are implemented and fresh-migration checked. The local
  95-table RLS/grant/immutability audit and disposable backup/restore drill pass; repeat both
  against CockroachDB Cloud before submission.

- [ ] **5. Prove the correctness kernel on real CockroachDB**
  Build: database-time claim/lease/generation, committed snapshot, controlled barrier, checkpoint, stale finalization, one direct replacement, bounded chain, lease takeover, durable duplicate suppression and atomic qualified introduction.
  Accept: v1 emits no result after v2 activation; one replacement cites v2; old generation cannot write; repeated outbox/finalization/effect calls leave counts at one; `40001` exhaustion is visible.
  Verify: deterministic barrier, concurrent finalizer, worker-kill/takeover and duplicate-delivery integration tests.
  Progress: the live suite proves database-time leases, expired-lease takeover with a larger generation, old-worker fence rejection, stale v1 invalidation, one v2 replacement, durable outbox handling, one introduction and visible bounded retry exhaustion. Hosted ECS worker-stop evidence remains open.

- [ ] **6. Implement DVI and Bedrock agent quality**
  Build: separate private buyer and buyer-safe Product Bundle vector spaces; Titan V2 metadata; resumable corpus loader; typed Bedrock Converse runtime/tools; Guardrails; budgets; deterministic replay and labelled evaluation set.
  Accept: semantic query finds the expected candidate; relational gates exclude stale/private/ineligible rows; citations are bundle subsets; hard-gate/tool/schema/leakage tests are 100%; fit classification and groundedness meet `architecture.md` thresholds.
  Verify: vector query plan/candidate artifact, live provider smoke, deterministic agent suite and committed evaluation report.
  Progress: DVI/current-version retrieval, Titan 1,024-dimensional contract, typed Converse tool loop, grounding checks and guardrail boundaries are implemented and locally tested. Live Nova/Titan access passes; both the deterministic five-case boundary report and the five-case live Nova qualification-quality gate pass at 100%. The live report stores only metrics, IDs, token counts and hashes. Live Guardrail intervention remains open.

- [ ] **7. Implement SQS/S3/observability adapters**
  Build: preseed checksum-verified S3 evidence; Cockroach outbox dispatcher to SQS FIFO; role-configured consumer; durable receipt; bounded retry/DLQ policy; sanitized correlation logs and P0 metrics.
  Accept: dispatcher crash/redelivery is harmless beyond FIFO's dedup window; message deletion follows result commit; secrets/private prompts are absent from logs.
  Verify: adapter contract tests, duplicate/redrive integration test, IAM policy assertions and log scan.
  Progress: checksum/version-bound interactive S3 upload, FIFO publisher, dispatcher, qualification consumer, durable receipt, DLQ policy/redrive controls, CloudWatch resources and IAM assertions are implemented. Hosted redrive and log-scan evidence remain open.

- [ ] **8. Implement P0 API and fail-closed composition**
  Build: briefs, missions/events, v2 bundle publication, engagement/response, decision approval/rejection, consent/introduction and integrity endpoints with auth-derived parties, idempotency and ETags.
  Accept: OpenAPI matches implementation; hosted dependencies reject missing Cockroach/AWS/auth configuration; stable errors include problem/cause/recovery/trace; no fixture winner appears.
  Verify: API contract/auth/idempotency/conflict tests and OpenAPI/client generation checks.
  Progress: the P0 lifecycle API, role projections, ETags/idempotency, integrity view, `/health` liveness and `/ready` Cockroach readiness are implemented; OpenAPI/client checks pass. Hosted auth/dependency proof remains open.

- [ ] **9. Implement the six P0 UI routes**
  Build: `/sira`, `/sira/missions/[id]`, `/seil/products/[id]/evidence`, `/seil/opportunities/[id]`, `/matches/[id]`, `/integrity/[missionId]` over live APIs.
  Accept: each route has loading/empty/partial/error/conflict/stale/success states; controlled race is understandable without console access; keyboard/mobile/WCAG checks pass; no broad unrelated component rewrite.
  Verify: web lint/type/build, browser E2E, accessibility/responsive checks and full local Cockroach journey.
  Progress: all six routes and versioned company-context UI are implemented; web lint/type/build pass. A repeatable Playwright/axe suite passes 14 desktop/mobile route, WCAG A/AA, overflow and keyboard/setup-state checks and caught/fixed one invalid ARIA loading-state contract. A fully authenticated browser journey and controlled race remain open.

- [ ] **10. Deploy the isolated hackathon-demo stack on AWS**
  Build: minimal CDK/ECR/ALB/ECS/SQS/S3/IAM/Secrets/CloudWatch; separate web/API/worker images; production configuration omits the demo controller module/route/permission.
  Accept: public HTTPS flow works without local services; task roles are least-privilege; secrets remain server-only; deployment/rollback and health/readiness work.
  Verify: CDK synth/assertions, image scan, hosted smoke, task-role review and redacted traces.
  Progress: CloudFront VPC origin, internal ALB, private ECS web/API/dispatcher/qualification services, SQS/DLQ, S3, Secrets, Guardrail, logs/alarms/dashboard and least-privilege roles synth and test successfully; images smoke locally. The web image explicitly enables the API-issued signed guest-session mode used by the production API. A credential-safe deployment preflight blocks CDK unless AWS identity/region, exact secret shape, remote verified-TLS Cockroach target, distinct SQL roles and independent signing keys pass. Cloud deployment and hosted smoke remain open.

- [ ] **11. Prove Managed MCP integrity and freeze evidence**
  Build: sanitized read-only views for current dependencies, attempts/fences/replacements, effect counts and DVI plan inputs; run MCP from a separate scoped identity.
  Accept: MCP verifies the same mission/decision IDs shown in UI; five consecutive hosted rehearsals yield identical invariant counts; scorecard claims match evidence.
  Verify: MCP transcript/manifest pinned to commit, demo runbook, repository/license/disclosure/secret scan and manual rubric audit.

## P1 after every P0 gate

- [x] Buyer versioned company-context editing, history/retirement, mission pinning and durable decision inbox.
- [x] Seller product portfolio, durable opportunity inbox and interactive versioned S3 ingestion.
- [x] Public marketplace search/product pages backed by Bedrock embeddings, DVI and relational active Product Bundle gates.
- [ ] Cockroach Cloud managed restore and hosted telemetry evidence. A disposable local backup/restore verifier, versioned settings/disclosure controls, tenant-safe marketplace analytics and safe DLQ status/start/cancel controls are implemented.
- [ ] `ccloud` provision/doctor/backup/restore evidence and GitHub Actions OIDC delivery. Credential-safe doctor and exact-repository OIDC workflow are implemented; Cloud authentication/deployment evidence remains open.

## P2 after P1 or when independently safe

- [x] Human-approved provider-neutral payment handoff. Exact-offer locking, role-separated approval, immutable handoff context, single-use open recording, and tests are implemented. SIRA never receives payment credentials or infers payment success.
- [ ] Bedrock Automated Reasoning as an explanatory policy check, never authority. A
  versioned formal bilateral-consent/purchase-authority policy, cross-Region Guardrail
  attachment, least-privilege invocation permission, and sanitized `ApplyGuardrail`
  finding parser are implemented. The qualification worker runs the standalone review
  after generation, outside its Cockroach transaction, stores only the sanitized result,
  and exposes it beside the buyer decision. Its typed result hard-codes
  `authoritative=false` and `may_authorize=false`; non-zero policy usage and every finding
  class are tested. Live labelled-policy evaluation and fidelity evidence remain open.
- [ ] Two principal-locked AgentCore Runtimes without AgentCore Memory. Stateless ARM64 HTTP
  runtimes, signed invocation tickets, SIRA/SEIL audiences, IAM invocation adapter, committed
  labelled-corpus entrypoint, durable budgeted Cockroach lifecycle and sanitized failure path are
  implemented; CDK proves two runtimes/endpoints and zero Memory resources. Live deployment and
  invocation evidence remain open.
- [ ] Measured Cockroach changefeed, multi-region and regional-survival experiments. An
  authenticated, bounded Cockroach webhook to ARM64 Lambda to SQS FIFO bridge is implemented
  with stable per-event identity, explicit at-least-once/per-key-only semantics, resolved-watermark
  handling, source-row minimization and fail-closed tests. Its isolated private consumer discovers
  durable tenants, re-reads the authoritative active pointer, invalidates stale decisions and
  schedules one replacement through the ordinary outbox. Live changefeed delivery and regional
  latency/survival measurements remain open.
- [ ] Additional categories and broader outcome-learning surfaces. Tenant-safe buyer/seller analytics backed by canonical records and transactional outbox events are implemented.
