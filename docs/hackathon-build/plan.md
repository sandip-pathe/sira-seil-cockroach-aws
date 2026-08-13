# SIRA + SEIL CockroachDB x AWS master plan

Status: Approach B approved and implementation started on 2026-08-13.

## Outcome

Build a qualified two-sided B2B agent marketplace. SIRA privately represents a buyer; SEIL privately represents sellers. CockroachDB prevents concurrent agents from creating stale, duplicate or lost buying outcomes. AWS hosts the product and provides model inference, embeddings, queueing, source-byte storage, secrets and telemetry.

The P0 commercial effect is one human-approved qualified introduction. PRAVA, offers, trials and purchasing are P2.

## Judge moment

1. SIRA starts a two-product meeting-intelligence comparison and snapshots active Product Bundles.
2. The cheaper product's v1 bundle says EU hosting is available.
3. After the real worker persists `SNAPSHOT_COMPLETE`, SEIL publishes a prevalidated v2 bundle correcting it to US-only.
4. The v1 attempt performs its real Bedrock work but loses finalization because its dependency is stale.
5. It emits no decision, match or introduction and creates one direct replacement.
6. The replacement cites v2 and blocks the cheaper product.
7. Buyer and seller humans consent; CockroachDB writes one qualified introduction.
8. Duplicate delivery and an expired-lease takeover leave one current decision, replacement and effect.
9. Managed MCP independently verifies the same IDs and invariants.

## Locked architecture

See `architecture.md` for the complete contract.

- CockroachDB Cloud v25.4+ on AWS is the sole transactional/business-state authority.
- DVI is candidate retrieval; relational current-version and eligibility gates decide use.
- Managed MCP is a read-only judge/operator integrity plane, not application transport.
- CloudFront is the public HTTPS edge; its VPC origin reaches an internal ALB routing to private Next.js and FastAPI ECS/Fargate services. Dispatcher and qualification workers are separate private ECS services.
- A Cockroach transactional outbox publishes to SQS FIFO; database consumer/effect keys handle redelivery.
- Existing agent/authority/guardrail code gains Bedrock Converse, Guardrails and Titan V2 adapters.
- P0 S3 evidence is preseeded/versioned/checksum-verified. Interactive ingestion is P1.
- Hosted mode fails closed; no fixture, model, identity or stale-vector fallback.

## Implementation sequence

### Phase 0: approved architecture and risk gates

- Synchronize `architecture.md`, this plan, checklist, spec/test/operations references and Devpost state.
- Record a cloud spending ceiling before provisioning.
- Prove AWS identity/region, Cockroach SQL/DVI/MCP/RLS/retry and Bedrock Converse/Guardrail/embedding access.

### Phase 1: Cockroach correctness kernel

- Add Cockroach-aware engine/driver configuration and a reusable whole-callback `40001` transaction runner.
- Add fresh migrations for buyer context, briefs, Product Bundles, embeddings, missions, attempts, dependencies, checkpoints, decisions, engagement/consent, introductions, idempotency, consumer receipts, events, outbox and effects.
- Add FORCE RLS and transaction-local verified tenant/principal/role context.
- Prove claim/snapshot/finalize, database-time leases, generation fences, stale invalidation, one direct successor, bounded replacement, durable deduplication and one P0 effect against a real CockroachDB instance.

### Phase 2: AWS and agent adapters

- Add `BedrockConverseRuntime`, typed tools, pinned model/prompt metadata and deterministic fake/replay runtime.
- Add Titan V2 embedding adapter and versioned vector repository with equality-prefix visibility/category filtering.
- Add Bedrock Guardrails for buyer/seller input and generated output; hard permission remains deterministic.
- Add preseeded S3 evidence adapter, SQS FIFO publisher/consumer, dispatcher leases and durable consumer receipts.
- Add sanitized correlation logs and P0 metrics.

### Phase 3: product API

- Implement active brief and two-bundle mission creation.
- Implement mission start/projection/event cursor, evidence-v2 publication, role-specific engagement, seller response, decision approval/rejection, consent, introduction and integrity endpoints.
- Require idempotency keys and `If-Match` where specified; errors expose problem, cause, recovery and trace ID.
- Compose production dependencies without fixture fallbacks.

### Phase 4: six-route P0 UI

- Extract only touched seams from the existing oversized components with characterization tests.
- Wire `/sira`, mission room, SEIL evidence correction, seller opportunity, match and integrity routes to live APIs.
- Cover loading, empty, partial, retry, stale/conflict, permission, provider failure and success states.
- Preserve the visual system while making the agent run and authority understandable before infrastructure details.

### Phase 5: deploy and prove

- Add minimal TypeScript CDK, ECR images, IAM task roles, Secrets Manager, ALB, ECS, SQS, S3 and CloudWatch configuration.
- Deploy web/API/worker, migrate the cloud cluster, seed evidence/vector corpus and run the controlled race.
- Configure read-only Managed MCP integrity views and evidence script.
- Run concurrency, security, browser, agent-evaluation, performance and five-rehearsal gates; capture sanitized evidence.

### Phase 6: P1/P2 only after P0

- P1: versioned company context, product management, interactive ingestion, public marketplace, inboxes/settings, full DLQ/restore operations, `ccloud`, GitHub OIDC and broader UI.
- P2: PRAVA, Automated Reasoning, AgentCore experiment, measured changefeed/multi-region, analytics and more categories.

## Cut lines

- A failed correctness kernel is a no-ship blocker. Stop breadth and fix it.
- Approach A can activate only after the kernel, DVI/MCP and Bedrock pass but SQS or six-route integration remains unstable. It keeps real Cockroach correctness, uses database outbox polling and consolidates into four screens.
- No P1/P2 work begins while any P0 authority, concurrency, tenant-isolation or hosted-path gate is red.

## Completion definition

P0 is complete only when current-state evidence proves every checklist item. Targets, local fixture results, deleted side repositories and screenshots without matching database IDs do not count.

## Current implementation evidence (2026-08-13)

Implemented and locally verified:

- Cockroach-aware engine, transaction-local tenant context, runtime-role/schema/RLS readiness, and whole-callback fresh-session `40001` retries;
- migrations through `cdb0010`, Product Bundles, DVI-backed retrieval, attempts/leases/fences/snapshots/replacements, durable receipts/effects, bilateral consent, introductions and append-only workspace settings;
- typed Bedrock Converse and Titan adapters, S3 content-addressed evidence, SQS FIFO outbox/consumer boundaries, and role-separated worker entrypoints;
- the six P0 product routes plus editable versioned company context, durable buyer/seller inboxes, interactive S3 evidence ingestion, public DVI-backed marketplace/product pages, settings/disclosure controls and buyer/seller analytics;
- CloudFront-to-internal-ALB ECS architecture, separate API/web/dispatcher/qualification services, S3/SQS/Secrets/Guardrail/CloudWatch resources, least-privilege task roles, and production images;
- PRAVA and controlled-merchant payment/reconciliation boundaries remain human-authorized and credential-isolated.

Evidence currently passing: the official repository gate (`358 passed`, `12` default live-Cockroach skips, coverage `75.33%`, Ruff/Mypy/architecture/OpenAPI/agent/client/web/credential checks), all `12` previously run live local Cockroach integration tests, a fresh migration to `cdb0010`/`90` public tables, an `85`-table zero-violation RLS/grant/immutability audit, a sanitized local backup/restore/digest/cleanup drill, live Nova Converse/Titan V2 provider smoke, and four CDK topology/IAM/AgentCore tests plus synth. API/web production images and smokes passed earlier; the newly added ARM64 AgentCore image cannot be locally built while Docker Desktop is unresponsive. These results prove local implementation and prior AWS model access, not hosted deployment.

Still externally gated or incomplete: CockroachDB Cloud TLS/managed backup/restore and Managed MCP evidence, live Guardrail intervention, AWS deployment/hosted rehearsals, a complete authenticated browser journey, live PRAVA, live AgentCore invocation, and Automated Reasoning/changefeed/multi-region experiments. The stateless AgentCore evaluation runtime and Cockroach-backed experiment lifecycle are implemented and synthesize with no AgentCore Memory; this does not substitute for deployed evidence. A five-case labelled live Nova qualification gate passes at 100%, and the disposable local restore drill passes, but neither substitutes for hosted evidence.
