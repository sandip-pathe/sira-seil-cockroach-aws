# SIRA + SEIL — Reverse-engineered replication PRD

> Historical audit snapshot from 16 October 2026, before the OpenAI/local-Python migration. It records the earlier system for reference and is not current setup or architecture guidance. See [README.md](../README.md) and [architecture-decisions.md](architecture-decisions.md) for the active design.

Audit date: 16 October 2026. Target: the source tree in this workspace. This is an implementation blueprint, not a proposal for a different product.

## Reading contract and evidence

The five requested sections describe product behavior and build order. The appendices supply the route inventory, HTTP contracts, database columns and constraints, configuration, and policy references needed to implement it precisely. File references are repository-relative so this document remains portable to a new workspace.

**Evidence priority:** executable routes/services/domain code and migrations override README and architecture prose; browser components establish which backend capabilities actually have screens. OpenAPI describes public wire contracts, but intentionally excludes several legacy routes, which are inventoried separately below. A source audit establishes implemented behavior; it does not establish that a cloud resource has been deployed or that a provider integration has passed a live test. No external product prices in fixtures were independently verified during this audit.

**Parity target:** preserve interfaces, state transitions, permission checks, exact arithmetic, data lineage, presentation, and failure behavior. Model-generated wording is inherently variable; replicate the pinned model/configuration and verified tool-result composition rather than promising identical prose for every turn.

## 1. PRODUCT OVERVIEW & CORE VALUES

### 1.1 Primary purpose

SIRA + SEIL is a company-aware B2B software buying and selling application. SIRA represents a buyer privately: it captures a buying mission, assembles requirements and company context, discovers and evaluates software, explains recommendations, and advances a selected plan through human authorization. SEIL represents a seller privately: it prepares structured, versioned Product Evidence, handles review/publication, and responds to qualified buyer needs. The two sides exchange explicitly released projections and exact commercial terms.

The product has three connected business paths:

1. **Buyer decision path:** request → versioned brief/rules → discovery/evaluation → explainable decision → feedback/calibration or plan selection → action run/purchase intent → approval → external payment handoff → outcome checkpoint.
2. **Seller evidence path:** find/claim product → draft and evidence → validation → review → immutable published pack → exports, activity, suspension or revision.
3. **Qualification path:** private company context + seller-visible brief + procurement policy → pinned product bundles → leased qualification attempt → dependency-validated decision → seller response → both parties' consent → one qualified introduction.

A separate bilateral exchange coordinator supports requirement release, evidence release, buyer offer, one seller counteroffer, exact acceptance, human approval, and an external handoff. Do not collapse these distinct workflows into one generic chat transcript.

### 1.2 Core values expressed in code

| Value | Required behavior |
|---|---|
| Company-specific fit | Requirements, current software stack, policy, constraints and preferences affect decisions. |
| Evidence before persuasion | Claims retain provenance, verification/freshness and source spans; retrieval similarity cannot override eligibility. |
| Privacy with minimum disclosure | Buyer context and seller drafts are private; only approved projections cross parties. |
| Human authority | Models propose tools and actions; server policy and humans authorize publication, consent, purchasing and disclosure. |
| Commercial neutrality | Product fee economics must not enter fit ranking; anti-fit is a legitimate response. |
| Reproducibility | Canonical hashes, pinned versions, snapshots, replay and immutable records explain historical decisions. |
| Concurrency correctness | Stale evidence cannot authorize a current decision or duplicate introduction. |
| Honest completion | Opening an external payment URL never means money moved or a subscription was fulfilled. |

### 1.3 Personas

| Persona | Goals and authority |
|---|---|
| Buyer requester / decision maker | Describe a need, inspect options, calibrate rules, select an exact plan and follow progress. |
| Procurement gate manager | Request approval and manage the selected procurement path. |
| Authorized human approver / executor | Approve, reject or revoke the exact purchase; perform protected handoff actions with required authentication. |
| Seller editor | Claim products, maintain evidence drafts, attach sources and submit for review. |
| Seller reviewer | Review an exact revision; approve or request changes according to server authority. |
| Platform operator / compiler | Manage platform-compiled evidence and operational recovery within explicit permissions. |
| Guest evaluator | Explore an isolated browser/identity workspace with reduced commercial authority. |
| Service principal / worker | Execute bounded system work; cannot substitute for a required human. |

These are capability roles, not necessarily separate paid account types. Firebase identities receive server-derived capabilities; generic introspection identities carry an explicitly allowlisted role set.

## 2. REVERSE-ENGINEERED FEATURE INVENTORY

### 2.1 Public website and entry points

**User actions:** view landing/product messaging, pricing, trust/security, privacy and terms; choose SIRA or SEIL sign-in; enter a workspace. Public routes are `/`, `/pricing`, `/security`, `/privacy`, `/terms`, `/sign-in`, `/sira/sign-in`, `/seil/sign-in`.

**Logic:** public pages are presentational components. Pricing is informational: there is no implemented SaaS subscription billing portal, Stripe checkout, invoice engine or plan-entitlement system. Preserve the actual copy/assets from `components/public`, rather than inferring a billing backend from the pricing page.

### 2.2 Identity, guests and workspace boundaries

**User actions:** anonymous Firebase sign-in, Google popup sign-in, email/password sign-in, account creation with verification email, Google linking to save a guest account, sign out/leave guest workspace; select buyer or seller mode.

**Logic:** Firebase ID tokens are verified server-side with rotating Google certificates, RS256, issuer, audience and required time claims. Password users require verified email for verified identity. Fresh authentication is required for step-up authority. A separate API-issued HMAC guest cookie path supports an isolated tenant, has expiry and a server-derived buyer/seller actor ID, and grants fewer capabilities. A Firebase anonymous SEIL user receives `seller_editor`, while an API-cookie SEIL guest receives `seller_viewer`; preserve this distinction.

Buyer Firebase capabilities include submit, view, select and procurement-gate management; verified identities additionally receive purchase approval/execution capabilities. Browser-supplied development identity headers are only trusted in development/test. Generic production tokens use an HTTPS introspection adapter and explicit role allowlist. Routers using `enforce_api_security` deny sellers every method/path except an exact allowlist, with participant/ownership checks afterward. The exchange router instead declares its own per-route human/capability checks and service participant guards. UI visibility alone is never authorization.

**Sources:** `identity.py`, `dependencies.py`, `guest_security.py`, `main.py`, `firebase-auth-provider.tsx`, `workspace-auth-gate.tsx`.

### 2.3 Chat-first SIRA and SEIL workspace

**User actions:** start a mission, submit a message, use suggested prompts, reopen conversation history, view product cards, open work/catalog/connectors/decisions/inbox panes, inspect artifacts and run events, respond to attention prompts, retry a failed message, expand/collapse panels and navigate on mobile.

**Logic:** `/v1/workspace/chat` accepts mode, optional conversation/mission identifiers, a message of 1–8,000 characters and at most 20 history entries. History messages have their own 12,000-character cap. Server-persisted missions, events, tasks, artifacts and checkpoints provide durable state; client history does not grant authority. Responses can contain products, verified tool names, advisory proposals, mission summary, attention, events and artifacts. Attention kinds are question, approval, credential, choice or blocked. Chat requires a configured real cognitive runtime; provider failures must not silently become canned success.

SIRA and SEIL use principal-specific context/tool sets. Mission lookup validates organization and mode. Advisory proposals identify whether human action is required; generating a proposal does not apply it. Connectors/capabilities report readiness and setup status; listing an integration name does not mean a working OAuth connector exists.

The default `build_kernel_tool_set` registers **14 read tools**, all contract `v1`, stage `evaluating`. SIRA tools: `search_published_products`, `get_published_product`, `get_purchase_request`, `get_purchase_brief`, `get_stack_snapshot`, `get_decision_view`, `get_decision_ledger`, `get_decision_counterfactuals`, `get_purchase_status`. SEIL tools: `search_seller_products`, `get_seller_product_view`, `get_seller_pack_draft`, `get_seller_pack_exports`, `get_engagement_requirement_brief`. Richer backend mutation APIs are not automatically callable through this default chat tool catalog.

Default turn budgets allow three model calls, four parallel reads, one mutation in the generic budget contract, 12,000 input tokens, 2,048 output tokens, a 90-second timeout and $0.25 cost ceiling; the SEIL context policy sets $0.20. Budget fields do not imply that the default catalog exposes mutation tools. The broker validates principal, party, purpose, stage, contract version and JSON input/output; protected-effect tools, when registered, require an active exact-scope capability grant.

**Sources:** `commerce-workspace.tsx`, `workspace_routes.py`, `workspace_service.py`, `workspace_schemas.py`, `cognitive_engine.py`, `python/agents/sira_agents`.

### 2.4 Company memory and workspace settings

**User actions:** through API, list/create/view/update/retire reusable company context; read/write buyer or seller settings; view profile/general/notifications/privacy panels; upgrade guest or sign out.

**Logic:** context kinds are REQUIREMENT, CONSTRAINT, STACK, POLICY, PREFERENCE and NOTE. Updates append versions and require a change reason; payloads cannot be empty. IDs supplied to a mission must be unique, tenant-owned and usable. Private inputs reject binary floating point recursively. Settings are party-scoped and versioned; notification/disclosure settings have typed validation and optimistic concurrency contracts. API support is broader than the visible profile modal: the modal renders mostly informational rows, English/light/India defaults and disconnected notification services. Do not invent editable profile fields or operational email delivery.

**Sources:** `qualification_schemas.py`, `qualification_service.py`, `profile-preview.tsx`, `workspace-account.ts`.

### 2.5 Catalog and marketplace discovery

**User actions:** browse product cards, search marketplace or seller product records, open product detail, inspect edition, pricing text, claims, integrations, source links, fit, limitations and evidence freshness.

**Logic:** distinguish workspace catalog responses, public buyer-safe marketplace projections, and seller-owned products. Marketplace retrieval uses Titan embeddings and CockroachDB vector indexes, followed by relational current-bundle/visibility checks. Embeddings are 1,024-dimensional. Seller-private drafts never become shared vectors. Research-only listings must be labeled `SEIL_RESEARCHED` / `RESEARCH_ONLY`; seller-published listings expose attestation separately. Static catalog overlays include real vendor names and dated public-source summaries; these are code content, not a live pricing feed. Missing catalog/provider configuration must produce the implemented unavailable state.

**Sources:** `qualification_catalog.py`, `qualification_service.py`, `workspace_service.py`, seller/search components.

### 2.6 Buyer requests, briefs and discovery

**User actions:** create a decision request, view request list/details and versioned decision room, trigger discovery, inspect brief/rules and candidate plans.

**Logic:** current procurement-native routes live under `/v1/decision-requests`; legacy purchase-request routes remain implemented but hidden from OpenAPI. Request creation uses idempotency and canonical request hashes. Purchase briefs are private; Requirement Briefs are explicitly seller-safe. Discovery/evaluation retains source snapshots, candidate membership, normalization/identity merges, pipeline versions and all inputs needed for replay. Asynchronous operations return workflow references/status. Historical decision version and route stage must remain consistent; stale route/version views cannot silently show a different actionable decision.

**Sources:** `routes.py`, `routes_v2.py`, `service.py`, `surface_v2.py`, `decision_room_projection.py`, `decision-surfaces.tsx`.

### 2.7 Deterministic decisions, graphs and explanation

**User actions:** compare options, inspect recommendation and alternatives, view eligibility gates, evidence and ledger details, examine counterfactuals, simulate changes, replay an evaluation and inspect robustness.

**Logic:** evaluate typed requirements, prohibitions, fit/anti-fit and evidence before ranking. Policy grammar uses TRUE/FALSE/UNRESOLVED; missing or ill-typed evidence is unresolved rather than implicitly passing. Only eligible and eligible-with-exception plans receive final ranks. Preserve exact lexicographic order:

1. Eligibility status.
2. Higher exact preference score.
3. Lower stack risk.
4. Lower total comparison-horizon cost.
5. Higher required evidence coverage.
6. Lower maximum evidence-age ratio.
7. Stable action identifiers, then plan identifier.

Comparisons require one currency and horizon unless an approved FX snapshot exists. Decimal/Fraction calculations reject binary float and boolean coercions in exact numeric inputs. Bounded graph ordering uses conservative preference/coverage and upper evidence age; optimistic/conservative envelopes determine whether the winner is stable. Missing bounds produce UNDETERMINED with reasons. Simulations/counterfactuals are explanatory and cannot mutate approval authority. Persist graph nodes, dependencies, gate results, score components/bounds, frontier and source snapshots, rather than storing only final prose.

**Sources:** `python/decision_engine/{evaluation,ranking,bounds,graph_v1,graph_v1_recall,counterfactual}.py`, `python/domain/rules.py`, `graph_persistence.py`, `graph_ledger.py`.

### 2.8 Feedback, calibration and rule proposals

**User actions:** give candidate/solution feedback, run calibration, inspect suggested preference or rule changes, accept/reject a proposal, reevaluate and select an exact plan.

**Logic:** feedback and calibration are durable records. A proposal is advisory until an authorized human accepts its exact version/hash. Proposal application validates scope and supported change types, supersedes outdated dependent state and reruns the relevant decision path. Preference weights have bounded exact values; a model cannot freely rewrite company policy. Rejected proposals do not become applied rules. Selection and execution are separate actions with separate permissions.

**Sources:** `clarification.py`, `service.py` calibration/proposal methods, `routes_v2.py`, `schemas_v2.py`.

### 2.9 Action plans, purchase intents and procurement approval

**User actions:** select a solution plan, start/view an action run, lock exact purchase terms, request approval, approve/reject/revoke, inspect purchase status and result artifacts.

**Logic:** actions must reference a current decision and valid selected plan. Locking a purchase binds exact decision/product/quote/commercial context into a canonical intent hash. Approval binds that exact intent; changed payloads supersede pending/approved authorization. Protected actions require appropriate capability, human identity and step-up where required. Approval expires and must be checked at use time; a displayed approved badge alone is insufficient.

Allowed approval state transitions: NOT_REQUESTED → PENDING; PENDING → APPROVED/REJECTED/REVOKED/EXPIRED/SUPERSEDED; APPROVED → REVOKED/SUPERSEDED. Rejected, revoked, expired and superseded are terminal in the pure transition service. Persist append-only approval events, actor identity and idempotent response records.

**Sources:** `state_machines.py`, `service.py`, `routes.py`, `routes_v2.py`, `schemas.py`, `schemas_v2.py`.

### 2.10 External payment handoff and post-purchase outcomes

**User actions:** prepare an approved handoff, inspect recipient/amount/currency/reference, open the external HTTPS payment page, view status, record outcome checkpoints, inspect the stackfile.

**Logic:** the application ends at a provider-neutral handoff. Persist the immutable destination, exact approved amount/reference, approval binding, expiry and hash. Opening requires current valid authority and matching handoff hash. READY can become OPENED, EXPIRED or CANCELLED; opening at/after expiry is rejected. OPENED is terminal in the pure handoff state machine and does not confirm payment. No card data, payment capture, payment-success webhook or automatic entitlement grant is implemented.

Outcome checkpoints validate intent/action status and supplied metrics, preserve provenance, and apply only authorized stack patches. Stack snapshots/patches have version/hash preconditions; changed stack state cannot be overwritten by a stale patch.

**Sources:** `commercial_terms.py`, payment/outcome methods in `service.py`, `domain/models.py`, `stackfile/models.py`, `stackfile/patches.py`.

### 2.11 Seller portfolio, drafts and evidence ingestion

**User actions:** search/select a product, claim it, view Product Evidence workspace tabs (pack, evidence, fit, review/publication and activity), inspect validation gaps and capabilities; through API, edit structured draft claims, attach existing evidence or upload content.

**Logic:** access requires seller ownership/capability and an eligible draft state. Editable states are SELLER_DRAFT, VALIDATION_CONFLICT and CHANGES_REQUESTED. Changes append a revision with hash/version preconditions. Approved publication fields are explicitly allowlisted. Required claims: product_name, public_summary, data_retention_days, supported_regions. Require at least one typed fit and anti-fit rule. Conflicting values for one claim produce CONFLICT; missing support produces HAS_GAPS. Retention requires evidence. Attachments must belong to the draft and explicitly support the referenced field. Missing/rejected evidence and evidence older than 365 days block a valid revision. Reattaching the same object with different source metadata conflicts.

Source classes: VENDOR_DOCUMENTATION, SECURITY_ATTESTATION, CONTRACT, PUBLIC_WEB, SELLER_ASSERTION. Ingestion supports UTF-8 plain text, Markdown, JSON and CSV, not arbitrary PDFs or Office files. The parser rejects empty or >25 MiB content and invalid UTF-8; upload-route/schema limits also apply. Normalize line endings, checksum bytes, persist immutable source identity and stable span offsets/hashes, and tag instruction-like source content as untrusted. Content-addressed S3 retains object version/checksum; development may use a local evidence store. Local span embeddings include a deterministic embedding implementation; do not confuse that with hosted Titan catalog retrieval.

**Sources:** `seller_service.py`, `seller_schemas.py`, `evidence_pipeline.py`, `evidence_repository.py`, `aws_services.py`, `seller-surfaces.tsx`.

### 2.12 Seller review, publication, export and suspension

**User actions:** submit exact draft revision for review, inspect review status, review approve/request-changes through authorized API, publish approved evidence, suspend a version, inspect/download export artifacts and activity metrics.

**Logic:** review submission and decision bind revision/content hashes and reviewer authority. A changed draft cannot reuse approval for an old payload. Publication creates immutable versioned packs and safe projections; publisher authority distinguishes SELLER_SEALED, PLATFORM_COMPILED and EXTERNAL_UNSEALED and must not imply independent verification of every claim. Prepare embedding/bundle candidates before the short atomic activation transaction; verify membership/hash and then advance active pointers together. Failure preserves old active truth; suspension/retraction removes eligibility. Do not expose private source URLs: publish only credential-free HTTPS URLs without query strings, with normalized host/path and no fragment. Exports derive from the published version, not the current mutable draft.

**Sources:** `publication.py`, `seller_service.py`, `qualification_repository.py`, `qualification_catalog.py`.

### 2.13 Qualification missions and stale-input recovery

**User actions:** create mission from private buyer context, selected company memory, seller-safe brief/criteria and procurement policy; inspect attempts/events, decision, approval and integrity proof.

**Logic:** mission creation pins context/brief/policy versions and active product bundles. A bundle binds product twin, safe catalog projection, eligible evidence, disclosure policy and embedding profile using ordered canonical digests. A worker claims a database-time lease and generation fence, saves its exact snapshot before network work, retrieves only permitted evidence and verifies output citations are a subset of eligible evidence. Finalization revalidates every invalidating dependency, including inputs not cited in prose. Changed inputs mark an attempt STALE and schedule/read one direct replacement, bounded to three replacements. Lost leases cannot write checkpoints or finalize. Mission and attempt state are separate from conversational mission state.

**Sources:** `qualification_service.py`, `qualification_repository.py`, `qualification_models.py`, `services/worker/sira_worker/qualification.py`.

### 2.14 Seller responses, dual consent and qualified introductions

**User actions:** open buyer/seller inbox, inspect party-safe engagement, respond FIT/ANTI_FIT/NEEDS_INFO, grant/revoke consent, approve a qualified decision and create/view an introduction.

**Logic:** participant organization/party is verified; sellers see only the released requirement projection. Responses and consents bind current engagement/decision/bundle digests and expiry. Positive fit is insufficient without current decision, both required human consents and valid engagement. Introduction execution revalidates all those conditions transactionally and reserves a single effect. Uniqueness and durable receipts prevent duplicate introduction under repeated clicks or delivery. Contact disclosure is a distinct protected boundary. Do not equate mutual consent, recommendation selection, purchase approval and payment authority.

**Sources:** qualification routes/service/repository; `marketplace_*`, `qualified_introductions` tables; `inbox-page.tsx`.

### 2.15 Bilateral exchange room and exact offers

**User actions:** create/open an exchange, copy seller link, release current evidence, propose exact line items, send one seller counteroffer, accept offer/counter, approve exact terms, prepare/open handoff and refresh projection.

**Logic:** signed route capabilities scope access to a case and expire; server additionally checks identity/party and membership. Buyer and seller commands have enforced ownership and `expected_version`. State path is CREATED → REQUIREMENT_RELEASED → EVIDENCE_RELEASED → OFFERED → COUNTERED (optional) → AGREED_PENDING_APPROVAL → APPROVED_FOR_HANDOFF. The pure compiler also defines REJECT/EXPIRE system commands; do not invent public endpoints for them. A buyer proposes and accepts seller counters; a seller counters or accepts the buyer offer. Offer line quantities are 1–1,000,000, at most 100 lines; amounts are exact nonnegative decimals, currency is three uppercase letters, and expiry matters. Acceptance/approval bind offer hash. Contract validation verifies total/lines and released evidence lineage. Private-plane field names are recursively prohibited from cross-party commands. Persist release manifests, hashed envelopes, recipient receipts, offer versions and approvals, with separate per-party projections.

**Sources:** `exchange-room.tsx`, `exchange_routes.py`, `exchange_service.py`, `exchange_schemas.py`, `domain/{bilateral_exchange,exchange_contracts,exchange_route}.py`, `bilateral_repository.py`.

### 2.16 Analytics, integrity and operational tools

**User actions:** inspect tenant-safe buyer/seller analytics, seller activity, dependency and recovery proof; operators run doctor, scenario, migration, restore/security/upgrade checks and safe DLQ inspection/redrive.

**Logic:** analytics are observational counts from canonical records/outbox activity, not causal conversion claims. Integrity shows pinned dependencies, vector candidates, attempts/fences, stale rejection, replacement and deduplication. Operational commands do not grant ordinary users admin access. Managed MCP is a read-only operator inspection path, not the runtime database transport. Scenario barriers/reset are restricted development/demo capabilities, omitted/disabled for production. CLI lifecycle commands include doctor/up/status/logs/check/down and evidence-race reset/run/verify.

### 2.17 Shared UX and state requirements

Reproduce loading, empty, unavailable, partial, error, stale/conflict and success views. Preserve safe error banners, explicit retry, pending-button disabling, native dialogs, keyboard close/focus behavior, accessible labels, responsive rails/panels and reduced-motion support. Use the existing CSS modules and assets as visual reference. The profile modal is informational; full CRUD for all domain models is not exposed there.

Visual baseline: warm canvas `#faf9f5`, white surfaces, ink `#1f1f1c`, muted text `#6f6a61`, SIRA blue `#0b5fff`, SEIL purple `#7c3aed`; Geist sans/mono and Montserrat branding; minimum page width 320 px. Brand and vendor artwork live in `apps/web/public`; screenshot references live in `docs/screenshots`.

## 3. ARCHITECTURE & SPECIFICATIONS

### 3.1 Stack and package boundaries

| Layer | Current implementation |
|---|---|
| Monorepo | pnpm workspaces, Python uv/Hatch packaging; app/package version 0.1.0. |
| Browser | Next.js 16.2.12 App Router, React/React DOM 19.2.8, TypeScript, CSS modules, Tailwind 4.3.3/PostCSS, Lucide icons, Pretext text layout. |
| Browser state/data | React hooks, TanStack React Query 5.101.4, generated `@sira/api-client`; no Redux store found. |
| Identity | Firebase JS SDK ^12.17.0; custom server-side Firebase JWT verification or RFC 7662-compatible introspection; signed guest cookies. |
| API | Python >=3.12,<3.14, FastAPI, Starlette, Uvicorn, Pydantic v2/settings; REST plus workflow SSE. |
| Persistence | SQLAlchemy 2 async, sqlalchemy-cockroachdb, asyncpg; psycopg for supporting SQL tooling; Alembic. |
| Database | CockroachDB; local Compose pins 25.4.14, architecture targets Cloud Standard 25.4+. SQLite/PostgreSQL compatibility exists for test/local migration paths, not production parity. |
| AI | boto3/botocore Bedrock Converse, default `us.amazon.nova-2-lite-v1:0`; Titan `amazon.titan-embed-text-v2:0`, 1,024 dimensions; Guardrails; optional explanatory Automated Reasoning. |
| Hosted runtime | Separate stateless principal-locked SIRA/SEIL AgentCore runtimes, signed scoped runtime tickets, no DB credentials or AgentCore Memory. |
| Async/storage | Transactional CockroachDB outbox → SQS FIFO/DLQ → worker; S3 immutable evidence objects and KMS; isolated changefeed hint queue. |
| Infrastructure | TypeScript AWS CDK 2.264.0, constructs 10.8.1; ECS/Fargate, private ALB, CloudFront, IAM, Secrets Manager, CloudWatch, Lambda/changefeed support and GitHub OIDC. |
| Web hosting | Vercel topology described in docs; same-origin Next rewrites proxy API paths to configured backend. `Dockerfile.web` also exists as a build artifact. |
| Quality | pytest/pytest-asyncio/Hypothesis, Ruff/mypy, JSON Schema contracts, Playwright 1.55.0, axe 4.10.2, ESLint 9.39.5, Prettier 3.6.2. |

Root pnpm is 11.9.0 and Node >=22. Root TypeScript pins 5.9.2; web pins 6.0.3; preserve these workspace differences. Python package declarations use ranges: exact resolved versions belong to `uv.lock`, not guessed point versions. JS ranges resolve through `pnpm-lock.yaml`. The generated dependency appendix records both declaration and lockfile evidence.

### 3.2 Ten critical packages/services

| Dependency | Why it matters |
|---|---|
| Next.js / React | Routing, rendering, browser state and interactive surfaces. |
| TanStack React Query | Queries, mutations, invalidation and pending/error UI. |
| FastAPI / Pydantic | HTTP contracts, dependency guards, validation and OpenAPI. |
| SQLAlchemy / sqlalchemy-cockroachdb / asyncpg | Tenant transactions, mapped records and retry kernel. |
| Alembic | Ordered physical schema, RLS, indexes and grants. |
| boto3 / botocore | Bedrock, S3, SQS and hosted AWS integrations. |
| Firebase / PyJWT / cryptography | Browser identities and verified server credentials. |
| rfc8785 | Canonical JSON used for content/intent/projection/contract digests. |
| AWS CDK | Reproducible roles, services, queues and runtime topology. |
| pytest / Hypothesis / Playwright | Business invariants, concurrency/property and browser contracts. |

### 3.3 Runtime topology and authority

```text
Browser -> Next.js -> same-origin /v1 rewrite -> CloudFront -> private ALB -> FastAPI
                                                                      |
                                +-------------------------------------+----+
                                |                                          |
                     CockroachDB authority                    principal-locked AgentCore
                     (tenant/private/catalog,                 -> Bedrock proposal/reasoning
                      journal and outbox)                     -> typed server validation
                                |
                     outbox dispatcher -> SQS FIFO -> qualification worker
                                                       | Bedrock/Titan/S3 work
                                                       + fenced DB finalization

Changefeed -> authenticated Lambda -> isolated FIFO hints -> re-read DB -> invalidation/outbox
```

Domain imports no adapters/frameworks. Agent contracts import no persistence/transport/worker code. Persistence imports no integration/transport/worker code. Architecture tests enforce these dependency directions. Models have no direct permission to commit commerce. Run journals/checkpoints/tool invocations are durable; network calls occur outside retryable database callbacks.

Production settings are stricter than some prose: `APP_ENV=production` requires CockroachDB, fixture/reset off, cognitive kernel and principal isolation on, `AGENT_RUNTIME_PROVIDER=agentcore`, both runtime ARNs and a >=32-byte ticket key. Local development defaults to direct Bedrock. Rebuild these settings gates exactly.

### 3.4 Data model blueprint

The full table-by-table dictionary below is extracted from both SQLAlchemy model files, including mapped fields, types, nullable/default/key definitions, inherited mixin fields and declared constraints. Migrations `cdb0001` through `cdb0018` remain authoritative for physical DDL, vector indexes, tenant policies, grants and changes not represented as ORM columns. Do not use ORM `create_all` as a production migration replacement.

| Aggregate | Relationships and purpose |
|---|---|
| Organization | Tenant root for private records; composite tenant/object references prevent cross-tenant links. |
| Buyer request | Purchase request → purchase brief versions → seller-safe requirement versions → immutable decision source snapshots. |
| Decision graph | Request → discovery/evaluation runs → candidate membership, identity merges, plans/components, gate/evidence/score results, bounds/frontiers and counterfactuals → decision record/version. |
| Calibration | Decision/brief → candidate feedback and calibration runs → human-decided proposals and successor decision versions. |
| Procurement | Decision → intent → approval requests/events → payment handoff; action runs/result artifacts and outcome checkpoints retain execution/outcome lineage. |
| Stack | Organization → versioned stack snapshots → conditional patches. |
| Seller evidence | Product/claim ownership → draft → immutable revisions → attachments → review submission/decision → published pack version → suspensions/exports/activity. |
| Evidence provenance | Immutable source version → stable spans → claim/evidence bindings; object checksum/version identifies stored bytes. |
| Qualification catalog | Product twin + catalog projection + evidence versions → bundle/members → active bundle pointer; embeddings point to versioned eligible objects. |
| Qualification execution | Mission + pinned bundles → attempt → dependencies/checkpoints → decision/dependencies; attempt generation/lease and replacement links control recovery. |
| Marketplace | Engagement → isolated buyer/seller projections → responses and consent records → one qualified introduction; durable consumer receipts/effects deduplicate processing. |
| Cognitive journal | Run → steps/checkpoints/tool invocations/user events; runtime ticket uses prevent replay abuse. |
| Agent work | Mission → task DAG/events/checkpoints/artifacts → capability grants → effects and budgeted experiments. |
| Bilateral exchange | Case → commands/transitions → party projections; release manifests/envelopes/receipts; versioned offers → exact approvals → handoffs. |
| Cross-cutting | Idempotency records, outbox events and workflow runs preserve retries and asynchronous progress. |

JSON payload columns are deliberate versioned domain objects; their shape is defined by Pydantic, frozen JSON Schema contracts and compilers. Do not infer that an arbitrary JSON column permits unrestricted client writes. Currency values use exact numeric types and hashes use the `sha256:` convention.

### 3.5 API map and wire conventions

The generated API appendix inventories every operation in `contracts/openapi/openapi.json`, with path/header/query parameters, body media type/schema and success/error response schemas. The following contract dictionary expands every referenced schema with required fields, types, enums, defaults and limits. An additional route-source appendix lists hidden legacy endpoints and route-specific guard calls. There is no GraphQL API in the audited code.

Shared behavior:

- Protected requests use verified bearer identity or signed guest session; `X-Workspace-Mode` chooses sira/seil but cannot override server identity.
- Idempotent mutations require `Idempotency-Key` where declared (8–128 characters); preserve a key across retries of the same user action. Reusing it for a different payload conflicts.
- Commands bind expected versions and/or hashes; return conflicts instead of applying stale mutations.
- Errors use `{ "error": { "code", "message", "request_id", "retryable", "next_action", "details" } }` according to the declared envelope. Codes commonly map to 400 semantic error, 401 authentication, 403 authority, 404 inaccessible/missing, 409 stale/hash/state conflict, 422 schema error, 429 rate limit, 502 provider rejection and 503 dependency unavailable.
- Create operations commonly return 201, accepted workflows 202, queries/actions 200; exact statuses are enumerated per route below. Workflow event transport includes `text/event-stream`; qualification mission events are a separate event-list contract.
- `/health` is liveness, `/ready` checks database readiness/security/schema conditions. Readiness and provider preflight are distinct; do not call a provider integration live-verified based only on `/health`.

Illustrative chat request (IDs omitted to begin a mission):

```json
{"mode":"sira","message":"Find meeting intelligence for our consulting team","history":[]}
```

Its response contains `conversation_id`, `mission_id`, `message`, `mission` and optionally products/tools/proposals/events/artifacts/attention. IDs and text are runtime values, not fixed fixture strings.

Illustrative qualification body:

```json
{
  "buyer_context":{"employee_count":10},
  "company_context_item_ids":[],
  "requirement_brief":{
    "category":"meeting_intelligence",
    "goal":"Find a private meeting intelligence tool for our team",
    "seller_visible_requirements":{},
    "criteria":[{"id":"privacy","label":"Privacy","requirement":"No general model training on our content","priority":"MUST"}]
  },
  "procurement_policy":{}
}
```

This illustrates wire shape, not a guarantee of business eligibility with an empty policy/context. The service/compiler applies additional semantic requirements and available-catalog checks.

## 4. CRITICAL EDGE CASES & HIDDEN LOGIC

### 4.1 Concurrency and durable effects

1. Retry SQLSTATE `40001` by rerunning the entire deterministic callback in a fresh transaction/session. Default database retry budget is five attempts with bounded jitter starting from 25 ms. Never repeat an external model/payment/storage call inside that callback.
2. Write business changes and outbox reservation together. SQS FIFO deduplication alone is insufficient; persist consumer receipts and unique effect keys beyond the queue dedup window.
3. Acknowledge/delete queue messages only after database commit. Poison/failed work goes through bounded retry/DLQ handling; redrive preserves original logical identity.
4. Use DB time, lease owner and generation fence for every worker checkpoint/finalization. A recovered old worker cannot finalize after takeover.
5. Seller publication racing qualification invalidates the old snapshot. Retain the stale attempt for proof, create one direct replacement and prevent stale match/introduction effects.
6. Final decision dependency checks cover all invalidating input versions, not just cited evidence. Retired context, changed policy or retracted evidence can invalidate a decision.
7. Precompute embeddings and immutable candidate material before pointer activation. Partial S3/network work must not expose a half-published bundle.

### 4.2 Tenant, identity and disclosure guards

FORCE RLS derives the verified organization from transaction-local `application_name` (`sira-api.<organization>`). Validate tenant identifiers before SQL and reset scope through transaction lifetime/pool reuse. Runtime roles must be non-owner, non-admin and lack BYPASSRLS. RLS is defense against application mistakes, not a guarantee after SQL credential compromise. Dedicated catalog/worker roles and grants constrain shared data access.

Seller access on routers wired to `enforce_api_security` is deny-by-default for exact method/path pairs. Review new routes before adding them to that allowlist. The exchange router has independent route guards rather than this router dependency; preserve both enforcement paths. Participant ownership and route capability verification still apply. Humans, service identities, verified users and anonymous users have different authority; actor text in request JSON cannot grant it.

Cross-party exchange payloads reject private field markers recursively, including buyer_private, seller_private, hidden_budget, reservation_value, seller_floor, private_notes and private_source. Safe projection construction is the primary boundary; string rejection alone is not sufficient authorization. Never return raw private draft/context JSON as a convenience response.

Signed runtime tickets bind scoped manifests; replay records and pinned runtime principal prevent the hosted model from acting as a different party. AgentCore receives no SQL credentials. Automated Reasoning results are explanatory evidence, not a permission grant.

### 4.3 Validation and numerical traps

- Missing values under most rule operators return UNRESOLVED; `exists` has separate presence semantics. `all` short-circuits false semantically; `any` prioritizes true, while unresolved fields remain traceable.
- Booleans compare only to booleans for strict equality, preventing Python `True == 1` from satisfying a typed policy. Exact numeric inputs reject bool and float; NaN/Infinity are invalid.
- Dates must be timezone-aware where required; evidence time bounds must precede evaluation and SLAs must be positive.
- Preference/coverage weights are integers 1–5; satisfaction intervals satisfy 0 ≤ lower ≤ upper ≤ 1; preference score bounds remain 0–100. Risk aggregation uses the worst component.
- Total cost/ranking requires one currency and comparison horizon; do not sort display-price strings or round before authoritative comparison.
- Evidence IDs are scoped to their draft/bundle and claim field. A valid-looking citation to another tenant, unpublished source, wrong field or stale bundle is invalid.
- Strict API models forbid unknown fields where configured; workspace BaseModels are not all strict, so preserve per-model behavior rather than globally imposing one policy.

### 4.4 Authentication, middleware and error behavior

API guest cookies use `sira_guest` in development and `__Host-sira_guest` outside it, with signed payload, HttpOnly attributes and production security settings. HMAC verification uses constant-time comparison. Guest TTL defaults to seven days and is constrained to 1 hour–30 days; future-issued tokens beyond allowed skew fail verification. Firebase certificate cache is bounded and provider outages return a sanitized 503 rather than authenticating optimistically. Generic introspection rejects invalid issuer/audience, expired/inactive tokens, unsupported party/identity and unallowlisted roles.

Middleware handles request correlation, origin restrictions for unsafe requests, guest bootstrap/abuse controls and active-turn concurrency guards. It rejects protected requests whose numeric `Content-Length` exceeds 131,072 bytes (128 KiB). This applies to upload routes too, despite the evidence parser's 25 MiB ceiling; preserve and explicitly test the difference. The header check alone is not a streaming body-size enforcement guarantee.

Limits are 60 guest bootstraps/network/hour, 120 authenticated API requests/minute, 30 non-chat mutations/minute, and chat limits of 8/minute, 40/hour and 100/day. Only one chat per credential subject is active in one process; conflicts return `CHAT_ALREADY_RUNNING` and `Retry-After: 2`. The limiter is explicitly in-process; reproduce its limitation rather than claiming a distributed quota. Origin validation runs when an Origin header is present and is not a complete independent CSRF guarantee. Return 429 retry headers where implemented. Preserve safe validation/provider/database failure envelopes; do not return secrets or raw SDK exceptions.

### 4.5 Background work, inbound integrations and omissions

Implemented asynchronous processes: outbox dispatcher, qualification queue consumer, changefeed hint consumer and budgeted experiment coordinator. The authenticated changefeed Lambda writes hints to an isolated queue; the consumer rereads authoritative state before invalidation/replacement. It does not directly trust changefeed payloads as new business truth. Agent experiments retain budget, lifecycle, typed observations and sanitized failures; capability grants scope effects.

No general calendar cron scheduling subsystem, payment processor webhook, production card capture, email/Slack delivery connector or arbitrary web-scraping crawler was established by this audit. Quiet-hours/email settings and connector labels must not be mistaken for these integrations. Operational scripts/CI are distinct from a user-facing background scheduler.

### 4.6 Known parity gaps and source contradictions

| Finding | Replication instruction |
|---|---|
| Architecture docs mention `/sira/missions/[id]`, `/matches/[id]`, `/integrity/[missionId]` and other P0 pages. | Actual App Router inventory below is the source of truth; corresponding API capabilities can exist without these standalone pages. |
| Both procurement-native and hidden legacy HTTP interfaces exist. | Implement canonical routes first and preserve aliases/legacy contracts if whole-codebase compatibility is required. |
| Two handlers declare `GET /v1/decisions/{decision_id}`. | `main.py` registers `router_v2` before legacy `router`, so the v2 ledger handler wins route matching; the hidden legacy declaration is not a second independently reachable URL. |
| Fixture catalog and API catalog contain different fictional/real vendor overlays. | Keep explicit data-mode behavior and research labels; do not silently substitute fixtures on API failure. |
| Readiness docs discuss more provider checks than simple liveness. | Match executable readiness/startup/doctor checks; retain separate real provider smoke/evaluation gates. |
| Profile settings display preview/static values. | Preserve informational behavior; richer persistence APIs do not imply fully editable UI. |
| Hosted docs report some integrations as pending live evidence. | Infrastructure/source implementation is not deployment verification; obtain fresh live evidence in the clone. |
| Firebase guest linking changes anonymous status and tenant-prefix derivation. | Test tenant continuity explicitly; account linking alone does not establish a server-side tenant migration. |

## 5. STEP-BY-STEP REPLICATION ROADMAP

Each phase has a concrete exit gate. Build user flows incrementally, but do not ship protected actions before their authority and concurrency dependencies.

| Phase | Build from an empty folder | Exit gate |
|---|---|---|
| 0 — Freeze parity inputs | Archive schemas, lockfiles, fixtures, assets, screenshots, routes and source policy references; choose local and hosted profiles; record Apache-2.0/provenance obligations. | Every module/route/table in this blueprint maps to a build task; planned docs are distinguished from implemented screens. |
| 1 — Workspace and contracts | Create pnpm/uv monorepo, package boundaries, Next shell, FastAPI app and generated client pipeline; reproduce frozen JSON Schemas. | Imports and client generation/typecheck pass; no circular architecture dependencies. |
| 2 — Database foundation | Start Cockroach 25.4.14 locally; recreate all tables and migrations through cdb0018; add indexes, vector columns/indexes, uniqueness, FORCE RLS and least-privilege roles. | Migration head/readiness succeeds; negative cross-tenant SQL tests pass using reused pooled connections. |
| 3 — Domain kernel | Implement canonical hashing, Money, three-valued rules, eligibility, plan actions/conflicts/dependencies, exact ranking/bounds and stack patch preconditions. | Unit/property/frozen-contract tests reproduce fixture outputs and rank stability; no model dependency needed. |
| 4 — Authentication and errors | Add Firebase/introspection/guest signing, request context, seller method/path policy, origin checks, idempotency, safe error envelopes and rate controls. | Production rejects dev headers; guests cannot purchase; step-up/human and tenant negatives pass. |
| 5 — Evidence pipeline | Implement source objects/spans, checksums, draft/revisions, typed claims/fit rules, review and safe exports. Add local storage then S3/KMS adapter. | Unsupported/empty/stale/wrong-scope evidence fails; approved immutable pack publication and suspension work. |
| 6 — Catalog and company context | Add versioned context/settings, product twin/catalog/evidence versions, bundle compiler, active pointers and Titan/DVI search. | Only current buyer-safe published evidence is retrievable; failed embedding cannot advance pointers. |
| 7 — Buyer decision API | Implement requests/briefs, snapshots, discovery/evaluation graph persistence, ledger, calibration/proposals, simulation/replay and versioned decision projections. | API fixtures/contract tests agree with deterministic engine; replay retains original sources and pipeline versions. |
| 8 — Authority and execution | Implement selected plans/action runs, exact purchase intents, approval events/expiry/revocation, handoff creation/opening, outcome checkpoints and stack updates. | Stale/hash-changed/expired approvals cannot execute; opening handoff never reports payment success. |
| 9 — Durable qualification | Implement missions/attempts, snapshot-before-network, lease/fence recovery, dependencies, stale finalization, replacement limits, outbox/receipts/effects; connect SQS/DLQ. | Evidence-race produces stale rejection, one replacement and one current decision; takeover and duplicate delivery tests pass on real Cockroach. |
| 10 — Bilateral marketplace | Implement party projections, seller response, dual consent, decision approval and atomic introduction. Add exchange route capabilities, manifests/envelopes, offers/counter/accept/approval/handoff. | Cross-party private data never leaks; concurrent/repeated introductions and handoffs retain exactly one authorized effect. |
| 11 — Cognitive runtime | Build typed tool catalog/broker, bounded context assembly, model proposal validation, verified response composer, durable cognitive journal, signed AgentCore tickets and principal isolation. | Real Converse/Titan smoke checks pass; injection/malformed tool calls and ticket replay cannot change protected state. |
| 12 — Browser integration | Build public pages/sign-in, SIRA/SEIL chat shells, catalog/product cards, decisions and room stages, seller tabs/review dialog, inbox, exchange room and profile modal; wire React Query/generated client. | Every actual App Router route renders correct loading/empty/error/stale/success states; API mode never falls back to fixture success. |
| 13 — Visual/accessibility parity | Restore brand/product assets, exact tokens/fonts/CSS layouts, mobile rails/dialogs, keyboard behavior and reduced motion. | Playwright/axe checks and visual comparisons against repository screenshots pass at desktop/mobile sizes. |
| 14 — Hosted operations | Recreate CDK services/IAM/queues/S3/KMS/secrets/OIDC/CloudFront/private ALB and Vercel rewrites; deploy isolated AgentCore runtimes; add changefeed hint ingress and telemetry. | Production safety settings pass; real TLS/RLS/vector/provider/race/dedup tests pass against deployed dependencies. |
| 15 — Full acceptance and recovery | Recreate analytics/integrity/CLI/evaluations, restore/security/upgrade drills, DLQ tools, CI and provenance docs; rehearse full flows. | Five consecutive clean end-to-end rehearsals; restore/recovery evidence; no stale decision, duplicate effect or false provider success. |

### 5.1 Required acceptance scenarios

1. New isolated guest enters SIRA, starts a mission, receives a real bounded response and can reopen persisted work.
2. A seller edits evidence, resolves validation gaps, submits a precise revision, obtains review and publishes a buyer-safe immutable version.
3. A buyer compares eligible plans; a cheaper policy-failing option cannot outrank an eligible one. An honest anti-fit remains visible without becoming a valid purchase candidate.
4. Calibration proposals require human acceptance; simulation/replay cannot grant purchase approval.
5. A human selects a plan, locks a current quote/intent, approves the exact hash and opens an external handoff; expired or changed authority is rejected.
6. Seller v2 publication races a v1 worker: old attempt becomes STALE, one replacement cites current inputs, and no stale introduction is emitted.
7. Duplicate SQS delivery and worker takeover produce one durable effect, including after the FIFO dedup window.
8. Seller FIT plus only one consent cannot introduce; valid dual consent plus current approval creates exactly one introduction.
9. Exchange buyer offer → seller counter → buyer acceptance → approval binds exact hashes; private inputs never appear in recipient projection.
10. Cross-tenant API/SQL/vector access, seller access to unlisted buyer routes, service-principal human actions and injected source instructions fail closed.
11. Provider/database outage shows an actionable safe error; it never produces a fictional completed run.
12. Guest Google upgrade is tested for data continuity and capability changes; any missing tenant migration is recorded as a known limitation rather than silently losing work.

### 5.2 Verification commands and limits

Use Python 3.12 or 3.13, Node >=22 and the repository-pinned pnpm. Install frozen lockfiles, migrate, then run the relevant checks:

```powershell
uv sync --all-extras
corepack pnpm install --frozen-lockfile
uv run pytest -q
powershell -ExecutionPolicy Bypass -File scripts/check.ps1
corepack pnpm --dir apps/web build
corepack pnpm test:browser
uv run sira-scenario reset --scenario evidence-race
uv run sira-scenario run --scenario evidence-race
uv run sira-scenario verify --latest
```

Live CockroachDB/AWS/Firebase/AgentCore tests require separately provisioned credentials and resources. This audit did not run the application, execute its test suite, or verify those external services. The following inventories were extracted statically to make this document checkable against source.


## Appendix A. Actual browser routes

Route groups do not appear in URLs. Redirects below are extracted from page source; components identify the rendered surface.

| URL | Implementation | Behavior |
|---|---|---|
| `/` | `apps/web/app/(public)/page.tsx` | Render: LandingPage |
| `/pricing` | `apps/web/app/(public)/pricing/page.tsx` | Render: PricingPage |
| `/privacy` | `apps/web/app/(public)/privacy/page.tsx` | Render: LegalPage |
| `/security` | `apps/web/app/(public)/security/page.tsx` | Render: SecurityPage |
| `/seil/sign-in` | `apps/web/app/(public)/seil/sign-in/page.tsx` | Render: SignInPreview |
| `/sign-in` | `apps/web/app/(public)/sign-in/page.tsx` | Render: SignInPreview |
| `/sira/sign-in` | `apps/web/app/(public)/sira/sign-in/page.tsx` | Render: SignInPreview |
| `/terms` | `apps/web/app/(public)/terms/page.tsx` | Render: LegalPage |
| `/decisions/[requestId]/versions/[version]/[stage]` | `apps/web/app/(workspace)/decisions/[requestId]/versions/[version]/[stage]/page.tsx` | Redirect: `/sira?decision=${encodeURIComponent(requestId)}&version=${encodeURIComponent(version)}&stage=${encodeURIComponent(stage)}` |
| `/decisions/new` | `apps/web/app/(workspace)/decisions/new/page.tsx` | Redirect: "/sira" |
| `/decisions` | `apps/web/app/(workspace)/decisions/page.tsx` | Redirect: "/sira/decisions" |
| `/exchange/[caseId]` | `apps/web/app/(workspace)/exchange/[caseId]/page.tsx` | Render: ExchangeRoom |
| `/home` | `apps/web/app/(workspace)/home/page.tsx` | Redirect: "/" |
| `/inbox` | `apps/web/app/(workspace)/inbox/page.tsx` | Redirect: "/" |
| `/seil/inbox` | `apps/web/app/(workspace)/seil/inbox/page.tsx` | Render: InboxPage |
| `/seil` | `apps/web/app/(workspace)/seil/page.tsx` | Render: CommerceWorkspace |
| `/seil/product-evidence/[productId]` | `apps/web/app/(workspace)/seil/product-evidence/[productId]/page.tsx` | Render: SellerProductWorkspace |
| `/seil/products/search` | `apps/web/app/(workspace)/seil/products/search/page.tsx` | Render: SellerProductSearch |
| `/seil/settings/profile` | `apps/web/app/(workspace)/seil/settings/profile/page.tsx` | Render: CommerceWorkspace, ProfileSettingsModal |
| `/seller` | `apps/web/app/(workspace)/seller/page.tsx` | Redirect: "/seil" |
| `/seller/product-evidence/[productId]` | `apps/web/app/(workspace)/seller/product-evidence/[productId]/page.tsx` | Redirect: `/seil/product-evidence/${productId}${field ? `?field=${encodeURIComponent(field)}` : ""}` |
| `/seller/products/search` | `apps/web/app/(workspace)/seller/products/search/page.tsx` | Redirect: "/seil/products/search" |
| `/settings/profile` | `apps/web/app/(workspace)/settings/profile/page.tsx` | Redirect: "/" |
| `/sira/decisions` | `apps/web/app/(workspace)/sira/decisions/page.tsx` | Redirect: "/sira?panel=decisions" |
| `/sira/inbox` | `apps/web/app/(workspace)/sira/inbox/page.tsx` | Redirect: "/sira" |
| `/sira` | `apps/web/app/(workspace)/sira/page.tsx` | Render: Record, CommerceWorkspace |
| `/sira/settings/profile` | `apps/web/app/(workspace)/sira/settings/profile/page.tsx` | Render: CommerceWorkspace, ProfileSettingsModal |

## Appendix B. Complete published REST API map

The checked-in OpenAPI contains **82 operations across 77 paths** and **201 component schemas**. Schema names resolve in Appendix C. `—` means no declared JSON body; it does not mean a route has no authentication. Common error envelopes also apply.

### `GET /health`

Operation: `health`. Health

Process liveness only; dependency failures must not trigger restart loops.

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/HealthResponse"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /ready`

Operation: `ready`. Ready

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/HealthResponse"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Required CockroachDB or cognitive runtime readiness checks failed | `application/json: {"$ref":"#/components/schemas/HealthResponse"}` |

### `GET /v1/action-runs/{action_run_id}`

Operation: `get_action_run`. Get Action Run

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `action_run_id` | path | True | `{"title":"Action Run Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/ActionRunView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/approval-requests/{approval_id}/approve`

Operation: `approve`. Approve

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `approval_id` | path | True | `{"title":"Approval Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/ApprovalCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/ApprovalRequestView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/approval-requests/{approval_id}/reject`

Operation: `reject_approval`. Reject Approval

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `approval_id` | path | True | `{"title":"Approval Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/ApprovalRejectCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/ApprovalRequestView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/approval-requests/{approval_id}/revoke`

Operation: `revoke_approval`. Revoke Approval

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `approval_id` | path | True | `{"title":"Approval Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/ApprovalRevokeCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/ApprovalRequestView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/capabilities`

Operation: `workspace_capabilities`. Workspace Capabilities

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"items":{"$ref":"#/components/schemas/CapabilityView"},"title":"Response Workspace Capabilities","type":"array"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/decision-requests`

Operation: `list_decision_requests`. List Decision Requests

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/DecisionIndexView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/decision-requests`

Operation: `create_decision_request`. Create Decision Request

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/DecisionRequestCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 201 | Successful Response | `application/json: {"$ref":"#/components/schemas/DecisionRequestView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/decision-requests/{request_id}`

Operation: `get_decision_request`. Get Decision Request

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `request_id` | path | True | `{"title":"Request Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/DecisionRequestView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/decision-requests/{request_id}/calibration-runs`

Operation: `run_decision_calibration`. Run Decision Calibration

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `request_id` | path | True | `{"title":"Request Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/CalibrationRunCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 201 | Successful Response | `application/json: {"$ref":"#/components/schemas/CalibrationRunView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/decision-requests/{request_id}/decision-rules`

Operation: `get_decision_rules`. Get Decision Rules

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `request_id` | path | True | `{"title":"Request Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/DecisionRulesView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/decision-requests/{request_id}/decision-view`

Operation: `get_decision_room`. Get Decision Room

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `request_id` | path | True | `{"title":"Request Id","type":"string"}` |
| `version` | query | False | `{"anyOf":[{"minimum":1,"type":"integer"},{"type":"null"}],"title":"Version"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/DecisionView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/decision-requests/{request_id}/discover`

Operation: `discover_decision_request`. Discover Decision Request

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `request_id` | path | True | `{"title":"Request Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 202 | Successful Response | `application/json: {"$ref":"#/components/schemas/WorkflowAccepted"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/decision-requests/{request_id}/solution-options/{solution_plan_id}/actions`

Operation: `record_solution_option_feedback`. Record Solution Option Feedback

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `request_id` | path | True | `{"title":"Request Id","type":"string"}` |
| `solution_plan_id` | path | True | `{"title":"Solution Plan Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/OptionFeedbackCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 201 | Successful Response | `application/json: {"$ref":"#/components/schemas/OptionFeedbackView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/decision-rules/{rules_id}/proposals/{proposal_id}/accept`

Operation: `accept_rule_proposal`. Accept Rule Proposal

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `rules_id` | path | True | `{"title":"Rules Id","type":"string"}` |
| `proposal_id` | path | True | `{"title":"Proposal Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/ProposalDecisionCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/ProposalDecisionView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/decision-rules/{rules_id}/proposals/{proposal_id}/reject`

Operation: `reject_rule_proposal`. Reject Rule Proposal

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `rules_id` | path | True | `{"title":"Rules Id","type":"string"}` |
| `proposal_id` | path | True | `{"title":"Proposal Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/ProposalDecisionCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/ProposalDecisionView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/decisions/{decision_id}`

Operation: `get_decision_ledger_v2`. Get Decision Ledger V2

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `decision_id` | path | True | `{"title":"Decision Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/DecisionLedgerV2"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/decisions/{decision_id}/action-runs`

Operation: `start_action_run`. Start Action Run

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `decision_id` | path | True | `{"title":"Decision Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/ActionRunCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 202 | Successful Response | `application/json: {"$ref":"#/components/schemas/ActionRunView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/decisions/{decision_id}/counterfactuals`

Operation: `get_counterfactuals`. Get Counterfactuals

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `decision_id` | path | True | `{"title":"Decision Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/CounterfactualView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/decisions/{decision_id}/plan-selections`

Operation: `select_action_plan`. Select Action Plan

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `decision_id` | path | True | `{"title":"Decision Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/PlanSelectionCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 201 | Successful Response | `application/json: {"$ref":"#/components/schemas/PlanSelectionView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/decisions/{decision_id}/purchase-intents`

Operation: `lock_purchase_intent`. Lock Purchase Intent

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `decision_id` | path | True | `{"title":"Decision Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/PurchaseIntentCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 201 | Successful Response | `application/json: {"$ref":"#/components/schemas/PurchaseIntentView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/decisions/{decision_id}/simulations`

Operation: `simulate_decision`. Simulate Decision

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `decision_id` | path | True | `{"title":"Decision Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/DecisionSimulationCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 201 | Successful Response | `application/json: {"$ref":"#/components/schemas/DecisionSimulationView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/demo/reset`

Operation: `reset_demo`. Reset Demo

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"additionalProperties":true,"title":"Response Reset Demo","type":"object"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/engagements/{engagement_id}/consent`

Operation: `record_consent`. Record Consent

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `engagement_id` | path | True | `{"title":"Engagement Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/ConsentCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/EngagementView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/evaluation-runs/{evaluation_run_id}/replay`

Operation: `replay_evaluation`. Replay Evaluation

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `evaluation_run_id` | path | True | `{"title":"Evaluation Run Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/EvaluationReplayView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/exchange-cases`

Operation: `create_exchange_case`. Create Exchange Case

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/ExchangeCaseCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 201 | Successful Response | `application/json: {"$ref":"#/components/schemas/ExchangeCaseCreated"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/exchange-cases/{case_id}`

Operation: `get_exchange_case`. Get Exchange Case

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `case_id` | path | True | `{"title":"Case Id","type":"string"}` |
| `route` | query | True | `{"maxLength":4096,"minLength":64,"title":"Route","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/ExchangeProjectionView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/exchange-cases/{case_id}/accept`

Operation: `accept_exchange_offer`. Accept Exchange Offer

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `case_id` | path | True | `{"title":"Case Id","type":"string"}` |
| `route` | query | True | `{"maxLength":4096,"minLength":64,"title":"Route","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/ExchangeOfferAccept"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/ExchangeProjectionView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/exchange-cases/{case_id}/approve`

Operation: `approve_exchange_offer`. Approve Exchange Offer

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `case_id` | path | True | `{"title":"Case Id","type":"string"}` |
| `route` | query | True | `{"maxLength":4096,"minLength":64,"title":"Route","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/ExchangeOfferApprove"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/ExchangeProjectionView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/exchange-cases/{case_id}/evidence`

Operation: `publish_exchange_evidence`. Publish Exchange Evidence

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `case_id` | path | True | `{"title":"Case Id","type":"string"}` |
| `route` | query | True | `{"maxLength":4096,"minLength":64,"title":"Route","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/ExchangeEvidencePublish"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/ExchangeProjectionView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/exchange-cases/{case_id}/handoffs`

Operation: `create_exchange_handoff`. Create Exchange Handoff

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `case_id` | path | True | `{"title":"Case Id","type":"string"}` |
| `route` | query | True | `{"maxLength":4096,"minLength":64,"title":"Route","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/ExchangeHandoffCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 201 | Successful Response | `application/json: {"$ref":"#/components/schemas/ExchangeHandoffView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/exchange-cases/{case_id}/handoffs/{handoff_id}/open`

Operation: `open_exchange_handoff`. Open Exchange Handoff

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `case_id` | path | True | `{"title":"Case Id","type":"string"}` |
| `handoff_id` | path | True | `{"title":"Handoff Id","type":"string"}` |
| `route` | query | True | `{"maxLength":4096,"minLength":64,"title":"Route","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/ExchangeHandoffOpen"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/ExchangeHandoffView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/exchange-cases/{case_id}/offers`

Operation: `propose_exchange_offer`. Propose Exchange Offer

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `case_id` | path | True | `{"title":"Case Id","type":"string"}` |
| `route` | query | True | `{"maxLength":4096,"minLength":64,"title":"Route","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/ExchangeOfferCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/ExchangeProjectionView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/organizations/{organization_id}/stackfile`

Operation: `get_stackfile`. Get Stackfile

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `organization_id` | path | True | `{"title":"Organization Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/StackfileView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/payment-handoffs/{handoff_id}/open`

Operation: `open_payment_handoff`. Open Payment Handoff

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `handoff_id` | path | True | `{"title":"Handoff Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/PaymentHandoffView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/purchase-intents/{intent_id}/approval-requests`

Operation: `create_approval_request`. Create Approval Request

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `intent_id` | path | True | `{"title":"Intent Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/ApprovalRequestCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 201 | Successful Response | `application/json: {"$ref":"#/components/schemas/ApprovalRequestView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/purchase-intents/{intent_id}/outcome-checkpoints`

Operation: `record_purchase_outcome`. Record Purchase Outcome

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `intent_id` | path | True | `{"title":"Intent Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/OutcomeCheckpointCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 201 | Successful Response | `application/json: {"$ref":"#/components/schemas/OutcomeCheckpointView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/purchase-intents/{intent_id}/payment-handoff`

Operation: `create_payment_handoff`. Create Payment Handoff

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `intent_id` | path | True | `{"title":"Intent Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 201 | Successful Response | `application/json: {"$ref":"#/components/schemas/PaymentHandoffView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/purchase-intents/{intent_id}/status`

Operation: `purchase_status`. Purchase Status

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `intent_id` | path | True | `{"title":"Intent Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/PurchaseStatusView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/qualification/analytics`

Operation: `qualification_get_workspace_analytics`. Qualification Get Workspace Analytics

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `days` | query | False | `{"default":30,"maximum":90,"minimum":1,"title":"Days","type":"integer"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/WorkspaceAnalyticsView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/qualification/company-context`

Operation: `qualification_list_company_context`. Qualification List Company Context

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `include_retired` | query | False | `{"default":false,"title":"Include Retired","type":"boolean"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/CompanyContextList"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/qualification/company-context`

Operation: `qualification_create_company_context`. Qualification Create Company Context

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/CompanyContextCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 201 | Successful Response | `application/json: {"$ref":"#/components/schemas/QualificationMutationView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/qualification/company-context/{item_id}`

Operation: `qualification_get_company_context`. Qualification Get Company Context

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `item_id` | path | True | `{"title":"Item Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/CompanyContextView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `PUT /v1/qualification/company-context/{item_id}`

Operation: `qualification_update_company_context`. Qualification Update Company Context

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `item_id` | path | True | `{"title":"Item Id","type":"string"}` |
| `If-Match` | header | True | `{"maxLength":100,"minLength":10,"title":"If-Match","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/CompanyContextUpdate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/QualificationMutationView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/qualification/company-context/{item_id}/retire`

Operation: `qualification_retire_company_context`. Qualification Retire Company Context

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `item_id` | path | True | `{"title":"Item Id","type":"string"}` |
| `If-Match` | header | True | `{"maxLength":100,"minLength":10,"title":"If-Match","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/QualificationMutationView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/qualification/decisions/{decision_id}/approval`

Operation: `qualification_decide_approval`. Qualification Decide Approval

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `decision_id` | path | True | `{"title":"Decision Id","type":"string"}` |
| `If-Match` | header | True | `{"maxLength":100,"minLength":10,"title":"If-Match","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/QualificationApprovalCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/QualificationMutationView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/qualification/engagements/{engagement_id}`

Operation: `qualification_get_engagement`. Qualification Get Engagement

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `engagement_id` | path | True | `{"title":"Engagement Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/QualificationEngagementView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/qualification/engagements/{engagement_id}/consents`

Operation: `qualification_record_consent`. Qualification Record Consent

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `engagement_id` | path | True | `{"title":"Engagement Id","type":"string"}` |
| `If-Match` | header | True | `{"maxLength":100,"minLength":10,"title":"If-Match","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/QualificationConsentCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 201 | Successful Response | `application/json: {"$ref":"#/components/schemas/QualificationMutationView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/qualification/engagements/{engagement_id}/introduction`

Operation: `qualification_create_introduction`. Qualification Create Introduction

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `engagement_id` | path | True | `{"title":"Engagement Id","type":"string"}` |
| `If-Match` | header | True | `{"maxLength":100,"minLength":10,"title":"If-Match","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/QualificationIntroductionCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 201 | Successful Response | `application/json: {"$ref":"#/components/schemas/QualificationMutationView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/qualification/engagements/{engagement_id}/responses`

Operation: `qualification_record_seller_response`. Qualification Record Seller Response

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `engagement_id` | path | True | `{"title":"Engagement Id","type":"string"}` |
| `If-Match` | header | True | `{"maxLength":100,"minLength":10,"title":"If-Match","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/QualificationSellerResponseCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 201 | Successful Response | `application/json: {"$ref":"#/components/schemas/QualificationMutationView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/qualification/inbox`

Operation: `qualification_get_inbox`. Qualification Get Inbox

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `limit` | query | False | `{"default":50,"maximum":100,"minimum":1,"title":"Limit","type":"integer"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/QualificationInboxView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/qualification/marketplace/products/{product_id}`

Operation: `qualification_get_marketplace_product`. Qualification Get Marketplace Product

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `product_id` | path | True | `{"title":"Product Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/PublicMarketplaceProductView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/qualification/marketplace/search`

Operation: `qualification_search_marketplace`. Qualification Search Marketplace

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `category` | query | True | `{"maxLength":80,"minLength":3,"title":"Category","type":"string"}` |
| `query` | query | True | `{"maxLength":1000,"minLength":3,"title":"Query","type":"string"}` |
| `limit` | query | False | `{"default":10,"maximum":30,"minimum":1,"title":"Limit","type":"integer"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/PublicMarketplaceSearchView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/qualification/missions`

Operation: `qualification_create_mission`. Qualification Create Mission

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/QualificationMissionCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 201 | Successful Response | `application/json: {"$ref":"#/components/schemas/QualificationMutationView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/qualification/missions/{mission_id}`

Operation: `qualification_get_mission`. Qualification Get Mission

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `mission_id` | path | True | `{"title":"Mission Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/QualificationMissionView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/qualification/missions/{mission_id}/events`

Operation: `qualification_get_mission_events`. Qualification Get Mission Events

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `mission_id` | path | True | `{"title":"Mission Id","type":"string"}` |
| `after` | query | False | `{"anyOf":[{"maxLength":64,"type":"string"},{"type":"null"}],"title":"After"}` |
| `limit` | query | False | `{"default":50,"maximum":100,"minimum":1,"title":"Limit","type":"integer"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/QualificationEventFeed"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/qualification/missions/{mission_id}/integrity`

Operation: `qualification_get_integrity`. Qualification Get Integrity

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `mission_id` | path | True | `{"title":"Mission Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/QualificationIntegrityView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/qualification/settings`

Operation: `qualification_get_workspace_settings`. Qualification Get Workspace Settings

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/WorkspaceSettingsView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `PUT /v1/qualification/settings`

Operation: `qualification_update_workspace_settings`. Qualification Update Workspace Settings

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `If-Match` | header | True | `{"maxLength":100,"minLength":10,"title":"If-Match","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/WorkspaceSettingsUpdate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/QualificationMutationView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/requirement-briefs/{brief_id}`

Operation: `get_requirement_brief`. Get Requirement Brief

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `brief_id` | path | True | `{"title":"Brief Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/RequirementBriefView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/seller/pack-drafts/{draft_id}`

Operation: `seller_evidence_get_draft`. Seller Evidence Get Draft

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `draft_id` | path | True | `{"title":"Draft Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/SellerPackDraftView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `PATCH /v1/seller/pack-drafts/{draft_id}`

Operation: `seller_evidence_patch_draft`. Seller Evidence Patch Draft

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `draft_id` | path | True | `{"title":"Draft Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/SellerPackDraftPatch"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/SellerPackDraftView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/seller/pack-drafts/{draft_id}/evidence`

Operation: `seller_evidence_attach_evidence`. Seller Evidence Attach Evidence

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `draft_id` | path | True | `{"title":"Draft Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/SellerEvidenceAttachCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 201 | Successful Response | `application/json: {"$ref":"#/components/schemas/SellerEvidenceAttachmentView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/seller/pack-drafts/{draft_id}/evidence/upload`

Operation: `seller_evidence_upload_evidence`. Seller Evidence Upload Evidence

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `draft_id` | path | True | `{"title":"Draft Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `multipart/form-data`: `{"$ref":"#/components/schemas/Body_seller_evidence_upload_evidence"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 201 | Successful Response | `application/json: {"$ref":"#/components/schemas/SellerEvidenceAttachmentView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/seller/pack-drafts/{draft_id}/publish`

Operation: `seller_evidence_publish`. Seller Evidence Publish

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `draft_id` | path | True | `{"title":"Draft Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/SellerPublishCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 201 | Successful Response | `application/json: {"$ref":"#/components/schemas/SellerPackVersionView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/seller/pack-drafts/{draft_id}/review-decisions`

Operation: `seller_evidence_review_decision`. Seller Evidence Review Decision

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `draft_id` | path | True | `{"title":"Draft Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/SellerReviewDecisionCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 201 | Successful Response | `application/json: {"$ref":"#/components/schemas/SellerReviewDecisionView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/seller/pack-drafts/{draft_id}/submit-review`

Operation: `seller_evidence_submit_review`. Seller Evidence Submit Review

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `draft_id` | path | True | `{"title":"Draft Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/SellerSubmitReviewCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/SellerPackDraftView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/seller/pack-versions/{version_id}/exports`

Operation: `seller_evidence_exports`. Seller Evidence Exports

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `version_id` | path | True | `{"title":"Version Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/SellerPackExportsView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/seller/pack-versions/{version_id}/suspend`

Operation: `seller_evidence_suspend`. Seller Evidence Suspend

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `version_id` | path | True | `{"title":"Version Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/SellerSuspendCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/SellerPackVersionView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/seller/products/search`

Operation: `seller_evidence_search_products`. Seller Evidence Search Products

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `q` | query | False | `{"anyOf":[{"maxLength":200,"minLength":2,"type":"string"},{"type":"null"}],"title":"Q"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/SellerProductSearchView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/seller/products/{product_id}/activity-metrics`

Operation: `seller_evidence_activity_metrics`. Seller Evidence Activity Metrics

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `product_id` | path | True | `{"title":"Product Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/SellerActivityMetrics"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/seller/products/{product_id}/claim`

Operation: `seller_evidence_claim_product`. Seller Evidence Claim Product

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `product_id` | path | True | `{"title":"Product Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |
| `Idempotency-Key` | header | True | `{"maxLength":128,"minLength":8,"title":"Idempotency-Key","type":"string"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/SellerClaimCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 201 | Successful Response | `application/json: {"$ref":"#/components/schemas/SellerClaimView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/seller/products/{product_id}/view`

Operation: `seller_evidence_product_view`. Seller Evidence Product View

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `product_id` | path | True | `{"title":"Product Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/SellerEvidenceView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/workflows/{workflow_id}`

Operation: `get_workflow`. Get Workflow

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `workflow_id` | path | True | `{"title":"Workflow Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/WorkflowView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/workflows/{workflow_id}/events`

Operation: `get_workflow_events`. Get Workflow Events

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `workflow_id` | path | True | `{"title":"Workflow Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Workflow status events | `text/event-stream: {"type":"string"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/workspace/catalog`

Operation: `workspace_catalog`. Workspace Catalog

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"items":{"$ref":"#/components/schemas/CatalogProductView"},"title":"Response Workspace Catalog","type":"array"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/workspace/catalog/{product_id}`

Operation: `workspace_product`. Workspace Product

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `product_id` | path | True | `{"title":"Product Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/CatalogProductView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `POST /v1/workspace/chat`

Operation: `workspace_chat`. Workspace Chat

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Body required: `True`.

- `application/json`: `{"$ref":"#/components/schemas/WorkspaceChatCreate"}`

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/WorkspaceChatView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/workspace/connectors`

Operation: `workspace_connectors`. Workspace Connectors

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"items":{"$ref":"#/components/schemas/ConnectorView"},"title":"Response Workspace Connectors","type":"array"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/workspace/conversations`

Operation: `workspace_conversations`. Workspace Conversations

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `mode` | query | True | `{"enum":["sira","seil"],"title":"Mode","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"items":{"$ref":"#/components/schemas/WorkspaceConversationView"},"title":"Response Workspace Conversations","type":"array"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |

### `GET /v1/workspace/missions/{mission_id}`

Operation: `workspace_mission`. Workspace Mission

Parameters:

| Name | Location | Required | Contract |
|---|---|---|---|
| `mission_id` | path | True | `{"title":"Mission Id","type":"string"}` |
| `X-Organization-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Organization-Id"}` |
| `X-Actor-Id` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Id"}` |
| `X-Actor-Roles` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Roles"}` |
| `X-Step-Up-Verified` | header | False | `{"default":false,"title":"X-Step-Up-Verified","type":"boolean"}` |
| `X-Identity-Kind` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Identity-Kind"}` |
| `X-Actor-Party` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Actor-Party"}` |
| `X-Workspace-Mode` | header | False | `{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Workspace-Mode"}` |

Request body: —

Responses:

| Status | Meaning | Media / schema |
|---|---|---|
| 200 | Successful Response | `application/json: {"$ref":"#/components/schemas/MissionSnapshotView"}` |
| 400 | Invalid request semantics | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 401 | Authentication failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 403 | Authority denied | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 404 | Resource unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 409 | State or hash conflict | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 422 | Contract validation failed | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 502 | Provider rejected the operation | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |
| 503 | Dependency or setup unavailable | `application/json: {"$ref":"#/components/schemas/ErrorEnvelope"}` |


## Appendix C. Exact HTTP model dictionary

Each block is the complete checked-in OpenAPI component schema, including nested references, required fields, enum values, bounds and defaults. `$ref` names resolve to another entry in this appendix. JSON Schema cannot express every service check; sections 2 and 4 and the guard/validator inventory supplement it.

### `ActionDescriptor`

```json
{"additionalProperties":false,"properties":{"expires_at":{"anyOf":[{"format":"date-time","type":"string"},{"type":"null"}],"title":"Expires At"},"href":{"maxLength":500,"pattern":"^/","title":"Href","type":"string"},"id":{"pattern":"^[A-Z][A-Z0-9_]{2,63}$","title":"Id","type":"string"},"label":{"maxLength":100,"minLength":1,"title":"Label","type":"string"},"method":{"enum":["GET","POST","PATCH","DELETE"],"title":"Method","type":"string"},"requires_confirmation":{"title":"Requires Confirmation","type":"boolean"}},"required":["id","label","method","href","requires_confirmation"],"title":"ActionDescriptor","type":"object"}
```

### `ActionRunCreate`

```json
{"additionalProperties":false,"properties":{"decision_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Decision Hash","type":"string"},"decision_version":{"minimum":1.0,"title":"Decision Version","type":"integer"},"solution_plan_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Solution Plan Id","type":"string"}},"required":["solution_plan_id","decision_version","decision_hash"],"title":"ActionRunCreate","type":"object"}
```

### `ActionRunView`

```json
{"additionalProperties":false,"properties":{"action_run_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Action Run Id","type":"string"},"action_type":{"enum":["REUSE_EXISTING","CONFIGURE_EXISTING","NO_ACTION","BUY","RENEW","RESIZE","REPLACE","CANCEL"],"title":"Action Type","type":"string"},"blocking_task":{"anyOf":[{"$ref":"#/components/schemas/BlockingTask"},{"type":"null"}]},"completed_at":{"anyOf":[{"format":"date-time","type":"string"},{"type":"null"}],"title":"Completed At"},"created_at":{"format":"date-time","title":"Created At","type":"string"},"current_step_id":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Current Step Id"},"decision_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Decision Hash","type":"string"},"decision_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Decision Id","type":"string"},"decision_version":{"minimum":1.0,"title":"Decision Version","type":"integer"},"execution_steps":{"items":{"$ref":"#/components/schemas/ExecutionStep"},"minItems":1,"title":"Execution Steps","type":"array"},"last_successful_checkpoint_id":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Last Successful Checkpoint Id"},"owner_role":{"$ref":"#/components/schemas/ActorRole"},"payment_handoff":{"anyOf":[{"$ref":"#/components/schemas/PaymentHandoffProjection"},{"type":"null"}]},"recovery_action":{"anyOf":[{"$ref":"#/components/schemas/ActionDescriptor"},{"type":"null"}]},"result_artifacts":{"items":{"$ref":"#/components/schemas/ResultArtifact"},"title":"Result Artifacts","type":"array"},"schema_version":{"pattern":"^[0-9]+\\.[0-9]+\\.[0-9]+$","title":"Schema Version","type":"string"},"selection_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Selection Id","type":"string"},"solution_plan_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Solution Plan Id","type":"string"},"status":{"$ref":"#/components/schemas/OperationStatus"},"updated_at":{"format":"date-time","title":"Updated At","type":"string"},"workflow_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Workflow Id","type":"string"}},"required":["schema_version","action_run_id","workflow_id","decision_id","decision_version","decision_hash","selection_id","solution_plan_id","action_type","status","current_step_id","last_successful_checkpoint_id","owner_role","execution_steps","payment_handoff","result_artifacts","created_at","updated_at","completed_at"],"title":"ActionRunView","type":"object"}
```

### `ActiveOperation`

```json
{"additionalProperties":false,"properties":{"current_checkpoint_id":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Current Checkpoint Id"},"id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Id","type":"string"},"kind":{"pattern":"^[A-Z][A-Z0-9_]{2,63}$","title":"Kind","type":"string"},"last_successful_checkpoint_id":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Last Successful Checkpoint Id"},"owner_role":{"$ref":"#/components/schemas/ActorRole"},"recovery_action":{"anyOf":[{"$ref":"#/components/schemas/ActionDescriptor"},{"type":"null"}]},"retryable":{"title":"Retryable","type":"boolean"},"safe_to_leave":{"title":"Safe To Leave","type":"boolean"},"started_at":{"format":"date-time","title":"Started At","type":"string"},"status":{"$ref":"#/components/schemas/OperationStatus"},"updated_at":{"format":"date-time","title":"Updated At","type":"string"}},"required":["id","kind","status","current_checkpoint_id","last_successful_checkpoint_id","owner_role","started_at","updated_at","retryable","safe_to_leave"],"title":"ActiveOperation","type":"object"}
```

### `ActorRole`

```json
{"enum":["REQUESTER","DECISION_MAKER","POLICY_REVIEWER","BUDGET_OWNER","PROCUREMENT","IT_OPERATIONS","AUDITOR","SELLER_EDITOR","SELLER_REVIEWER","PLATFORM_OPERATOR"],"title":"ActorRole","type":"string"}
```

### `AgentProposalView`

```json
{"properties":{"advisory_only":{"default":true,"title":"Advisory Only","type":"boolean"},"payload":{"additionalProperties":true,"title":"Payload","type":"object"},"proposal_hash":{"title":"Proposal Hash","type":"string"},"proposal_type":{"title":"Proposal Type","type":"string"},"ranking_effect":{"default":false,"title":"Ranking Effect","type":"boolean"},"requires_human_action":{"default":true,"title":"Requires Human Action","type":"boolean"}},"required":["proposal_type","proposal_hash","payload"],"title":"AgentProposalView","type":"object"}
```

### `ApprovalCreate`

```json
{"additionalProperties":false,"properties":{"actor_role":{"title":"Actor Role","type":"string"},"intent_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Intent Hash","type":"string"}},"required":["intent_hash","actor_role"],"title":"ApprovalCreate","type":"object"}
```

### `ApprovalProjection`

```json
{"additionalProperties":false,"properties":{"completed_count":{"minimum":0.0,"title":"Completed Count","type":"integer"},"expires_at":{"anyOf":[{"format":"date-time","type":"string"},{"type":"null"}],"title":"Expires At"},"href":{"anyOf":[{"maxLength":500,"type":"string"},{"type":"null"}],"title":"Href"},"owner_roles":{"items":{"$ref":"#/components/schemas/ActorRole"},"title":"Owner Roles","type":"array"},"rejected_by_role":{"anyOf":[{"$ref":"#/components/schemas/ActorRole"},{"type":"null"}]},"required":{"title":"Required","type":"boolean"},"required_count":{"minimum":0.0,"title":"Required Count","type":"integer"},"requirement_set_id":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Requirement Set Id"},"status":{"$ref":"#/components/schemas/ApprovalStatus"}},"required":["required","status","owner_roles","completed_count","required_count"],"title":"ApprovalProjection","type":"object"}
```

### `ApprovalRejectCreate`

```json
{"additionalProperties":false,"properties":{"actor_role":{"title":"Actor Role","type":"string"},"intent_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Intent Hash","type":"string"},"reason":{"maxLength":1000,"minLength":3,"title":"Reason","type":"string"}},"required":["intent_hash","actor_role","reason"],"title":"ApprovalRejectCreate","type":"object"}
```

### `ApprovalRequestCreate`

```json
{"additionalProperties":false,"description":"The server resolves approval policy from the locked Purchase Brief.","properties":{},"title":"ApprovalRequestCreate","type":"object"}
```

### `ApprovalRequestView`

```json
{"additionalProperties":false,"properties":{"approved_roles":{"items":{"type":"string"},"title":"Approved Roles","type":"array"},"expires_at":{"format":"date-time","title":"Expires At","type":"string"},"id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Id","type":"string"},"intent_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Intent Hash","type":"string"},"purchase_intent_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Purchase Intent Id","type":"string"},"required_roles":{"items":{"type":"string"},"title":"Required Roles","type":"array"},"status":{"$ref":"#/components/schemas/ApprovalStatus"}},"required":["id","purchase_intent_id","intent_hash","status","required_roles","approved_roles","expires_at"],"title":"ApprovalRequestView","type":"object"}
```

### `ApprovalRevokeCreate`

```json
{"additionalProperties":false,"properties":{"actor_role":{"title":"Actor Role","type":"string"},"intent_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Intent Hash","type":"string"},"reason":{"maxLength":1000,"minLength":3,"title":"Reason","type":"string"}},"required":["intent_hash","actor_role","reason"],"title":"ApprovalRevokeCreate","type":"object"}
```

### `ApprovalStatus`

```json
{"enum":["NOT_REQUIRED","NOT_REQUESTED","PENDING","APPROVED","REJECTED","REVOKED","EXPIRED","SUPERSEDED"],"title":"ApprovalStatus","type":"string"}
```

### `AttentionView`

```json
{"properties":{"kind":{"enum":["question","approval","credential","choice","blocked"],"title":"Kind","type":"string"},"options":{"items":{"type":"string"},"title":"Options","type":"array"},"prompt":{"title":"Prompt","type":"string"},"reason":{"title":"Reason","type":"string"}},"required":["kind","prompt","reason"],"title":"AttentionView","type":"object"}
```

### `BlockingTask`

```json
{"additionalProperties":false,"properties":{"due_at":{"anyOf":[{"format":"date-time","type":"string"},{"type":"null"}],"title":"Due At"},"expires_at":{"anyOf":[{"format":"date-time","type":"string"},{"type":"null"}],"title":"Expires At"},"href":{"maxLength":500,"pattern":"^/","title":"Href","type":"string"},"id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Id","type":"string"},"owner_role":{"$ref":"#/components/schemas/ActorRole"},"status":{"enum":["OPEN","WAITING","BLOCKED","COMPLETED","EXPIRED"],"title":"Status","type":"string"},"title":{"maxLength":200,"minLength":1,"title":"Title","type":"string"}},"required":["id","title","owner_role","due_at","expires_at","status","href"],"title":"BlockingTask","type":"object"}
```

### `Body_seller_evidence_upload_evidence`

```json
{"properties":{"claim_fields_json":{"maxLength":2000,"minLength":4,"title":"Claim Fields Json","type":"string"},"evidence_file":{"contentMediaType":"application/octet-stream","description":"Private source evidence, max 25 MiB","title":"Evidence File","type":"string"},"observed_at":{"anyOf":[{"format":"date-time","type":"string"},{"type":"null"}],"title":"Observed At"},"source_class":{"maxLength":80,"minLength":2,"title":"Source Class","type":"string"}},"required":["evidence_file","source_class","claim_fields_json"],"title":"Body_seller_evidence_upload_evidence","type":"object"}
```

### `BoundUnavailableView`

```json
{"additionalProperties":false,"properties":{"reason_code":{"pattern":"^[A-Z][A-Z0-9_]{2,63}$","title":"Reason Code","type":"string"},"status":{"const":"BOUND_UNAVAILABLE","default":"BOUND_UNAVAILABLE","title":"Status","type":"string"}},"required":["reason_code"],"title":"BoundUnavailableView","type":"object"}
```

### `CalibrationRunCreate`

```json
{"additionalProperties":false,"properties":{"current_approach_id":{"default":"current_manual_recap","maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Current Approach Id","type":"string"},"expected_qualifier_candidate_id":{"default":"fixture_selected_fit","maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Expected Qualifier Candidate Id","type":"string"},"known_failure_candidate_id":{"default":"fixture_low_price_policy_fail","maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Known Failure Candidate Id","type":"string"},"proposed_changes":{"items":{"additionalProperties":true,"type":"object"},"title":"Proposed Changes","type":"array"}},"title":"CalibrationRunCreate","type":"object"}
```

### `CalibrationRunView`

```json
{"additionalProperties":false,"properties":{"id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Id","type":"string"},"proposal":{"anyOf":[{"additionalProperties":true,"type":"object"},{"type":"null"}],"title":"Proposal"},"proposal_effective":{"const":false,"default":false,"title":"Proposal Effective","type":"boolean"},"purchase_brief_version":{"title":"Purchase Brief Version","type":"integer"},"purchase_request_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Purchase Request Id","type":"string"},"results":{"items":{"additionalProperties":true,"type":"object"},"title":"Results","type":"array"}},"required":["id","purchase_request_id","purchase_brief_version","results"],"title":"CalibrationRunView","type":"object"}
```

### `CapabilityView`

```json
{"properties":{"id":{"title":"Id","type":"string"},"label":{"title":"Label","type":"string"},"reason_code":{"title":"Reason Code","type":"string"},"remediation":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Remediation"},"status":{"enum":["disabled","misconfigured","ready","degraded","offline"],"title":"Status","type":"string"}},"required":["id","label","status","reason_code"],"title":"CapabilityView","type":"object"}
```

### `CatalogProductView`

```json
{"properties":{"billing_unit":{"title":"Billing Unit","type":"string"},"claims":{"items":{"type":"string"},"title":"Claims","type":"array"},"edition":{"title":"Edition","type":"string"},"evidence_freshness":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Evidence Freshness"},"evidence_status":{"anyOf":[{"enum":["PUBLISHED","RESEARCH_ONLY"],"type":"string"},{"type":"null"}],"title":"Evidence Status"},"fit":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Fit"},"id":{"title":"Id","type":"string"},"integrations":{"items":{"type":"string"},"title":"Integrations","type":"array"},"listing_origin":{"anyOf":[{"enum":["SELLER_PUBLISHED","SEIL_RESEARCHED"],"type":"string"},{"type":"null"}],"title":"Listing Origin"},"logo":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Logo"},"name":{"title":"Name","type":"string"},"price":{"title":"Price","type":"string"},"requirement_coverage":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Requirement Coverage"},"seller":{"title":"Seller","type":"string"},"seller_attested":{"anyOf":[{"type":"boolean"},{"type":"null"}],"title":"Seller Attested"},"source_refs":{"items":{"additionalProperties":true,"type":"object"},"title":"Source Refs","type":"array"},"status":{"title":"Status","type":"string"},"summary":{"title":"Summary","type":"string"},"website":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Website"},"why_company":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Why Company"}},"required":["id","name","seller","edition","price","billing_unit","status","summary","claims","integrations"],"title":"CatalogProductView","type":"object"}
```

### `CompanyContextCreate`

```json
{"additionalProperties":false,"properties":{"change_reason":{"maxLength":500,"minLength":3,"title":"Change Reason","type":"string"},"kind":{"enum":["REQUIREMENT","CONSTRAINT","STACK","POLICY","PREFERENCE","NOTE"],"title":"Kind","type":"string"},"label":{"maxLength":160,"minLength":2,"title":"Label","type":"string"},"payload":{"additionalProperties":true,"title":"Payload","type":"object"}},"required":["kind","label","payload","change_reason"],"title":"CompanyContextCreate","type":"object"}
```

### `CompanyContextList`

```json
{"additionalProperties":false,"properties":{"items":{"items":{"additionalProperties":true,"type":"object"},"title":"Items","type":"array"}},"required":["items"],"title":"CompanyContextList","type":"object"}
```

### `CompanyContextProjection`

```json
{"additionalProperties":false,"properties":{"company_profile_version":{"minimum":1.0,"title":"Company Profile Version","type":"integer"},"company_stack_snapshot":{"minimum":1.0,"title":"Company Stack Snapshot","type":"integer"},"facts_used":{"items":{"$ref":"#/components/schemas/CompanyFactProjection"},"title":"Facts Used","type":"array"},"hidden_fact_count":{"minimum":0.0,"title":"Hidden Fact Count","type":"integer"}},"required":["facts_used","hidden_fact_count","company_profile_version","company_stack_snapshot"],"title":"CompanyContextProjection","type":"object"}
```

### `CompanyContextUpdate`

```json
{"additionalProperties":false,"properties":{"change_reason":{"maxLength":500,"minLength":3,"title":"Change Reason","type":"string"},"label":{"maxLength":160,"minLength":2,"title":"Label","type":"string"},"payload":{"additionalProperties":true,"title":"Payload","type":"object"}},"required":["label","payload","change_reason"],"title":"CompanyContextUpdate","type":"object"}
```

### `CompanyContextView`

```json
{"additionalProperties":false,"properties":{"item":{"additionalProperties":true,"title":"Item","type":"object"},"versions":{"items":{"additionalProperties":true,"type":"object"},"title":"Versions","type":"array"}},"required":["item","versions"],"title":"CompanyContextView","type":"object"}
```

### `CompanyFactProjection`

```json
{"additionalProperties":false,"properties":{"display_name":{"maxLength":100,"minLength":1,"title":"Display Name","type":"string"},"display_value":{"maxLength":200,"minLength":1,"title":"Display Value","type":"string"},"fact_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Fact Id","type":"string"},"provenance_label":{"maxLength":200,"minLength":1,"title":"Provenance Label","type":"string"},"sensitivity":{"enum":["internal","confidential","restricted"],"title":"Sensitivity","type":"string"}},"required":["fact_id","display_name","display_value","provenance_label","sensitivity"],"title":"CompanyFactProjection","type":"object"}
```

### `ComponentStatus`

```json
{"enum":["ELIGIBLE","ELIGIBLE_WITH_EXCEPTION","CONDITIONAL","SIRA_INELIGIBLE","SEIL_PASS","UNAVAILABLE","STALE_EVIDENCE","INSUFFICIENT_EVIDENCE","CONFLICTING_EVIDENCE","AUTHORITY_REQUIRED","ADVISORY_ONLY"],"title":"ComponentStatus","type":"string"}
```

### `ConnectorView`

```json
{"properties":{"id":{"title":"Id","type":"string"},"meta":{"title":"Meta","type":"string"},"name":{"title":"Name","type":"string"},"purpose":{"title":"Purpose","type":"string"},"status":{"enum":["Healthy","Needs setup","Not connected","Proof workspace"],"title":"Status","type":"string"}},"required":["id","name","purpose","status","meta"],"title":"ConnectorView","type":"object"}
```

### `ConsentCreate`

```json
{"additionalProperties":false,"properties":{"consent":{"title":"Consent","type":"boolean"},"scope":{"const":"CONTACT_EXCHANGE","default":"CONTACT_EXCHANGE","title":"Scope","type":"string"}},"required":["consent"],"title":"ConsentCreate","type":"object"}
```

### `CostLineItemBoundsView`

```json
{"additionalProperties":false,"properties":{"base":{"anyOf":[{"$ref":"#/components/schemas/MoneyViewV2"},{"$ref":"#/components/schemas/BoundUnavailableView"}],"title":"Base"},"high":{"anyOf":[{"$ref":"#/components/schemas/MoneyViewV2"},{"$ref":"#/components/schemas/BoundUnavailableView"}],"title":"High"},"low":{"anyOf":[{"$ref":"#/components/schemas/MoneyViewV2"},{"$ref":"#/components/schemas/BoundUnavailableView"}],"title":"Low"},"schedule_version":{"anyOf":[{"maxLength":100,"type":"string"},{"type":"null"}],"title":"Schedule Version"},"type":{"enum":["MERCHANT_SUBTOTAL","SIRA_TRANSACTION_FEE","TAX","CONTRACT_COST","MIGRATION_COST","IMPLEMENTATION_COST"],"title":"Type","type":"string"}},"required":["type","low","base","high","schedule_version"],"title":"CostLineItemBoundsView","type":"object"}
```

### `CounterfactualRecordView`

```json
{"additionalProperties":false,"properties":{"after_evaluation_payload_hash":{"anyOf":[{"pattern":"^sha256:[0-9a-f]{64}$","type":"string"},{"type":"null"}],"title":"After Evaluation Payload Hash"},"after_selected_plan_id":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"After Selected Plan Id"},"alternative_fact_id_sets":{"items":{"items":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},"type":"array"},"title":"Alternative Fact Id Sets","type":"array"},"before_evaluation_payload_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Before Evaluation Payload Hash","type":"string"},"before_selected_plan_id":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Before Selected Plan Id"},"changed_gate_ids":{"items":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},"title":"Changed Gate Ids","type":"array"},"generic_evaluation_payload_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Generic Evaluation Payload Hash","type":"string"},"generic_selected_plan_id":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Generic Selected Plan Id"},"outcome":{"enum":["WINNER_CHANGED","NO_SMALL_COUNTERFACTUAL_FOUND"],"title":"Outcome","type":"string"},"record_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Record Hash","type":"string"},"removed_fact_ids":{"items":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},"maxItems":3,"title":"Removed Fact Ids","type":"array"},"tested_limit":{"const":3,"title":"Tested Limit","type":"integer"}},"required":["outcome","removed_fact_ids","alternative_fact_id_sets","tested_limit","before_evaluation_payload_hash","after_evaluation_payload_hash","generic_evaluation_payload_hash","before_selected_plan_id","after_selected_plan_id","generic_selected_plan_id","changed_gate_ids","record_hash"],"title":"CounterfactualRecordView","type":"object"}
```

### `CounterfactualView`

```json
{"additionalProperties":false,"properties":{"changed":{"title":"Changed","type":"boolean"},"company_aware_result_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Company Aware Result Hash","type":"string"},"company_aware_selected_candidate_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Company Aware Selected Candidate Id","type":"string"},"decision_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Decision Id","type":"string"},"decisive_private_fact_ids":{"items":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},"title":"Decisive Private Fact Ids","type":"array"},"explanation":{"title":"Explanation","type":"string"},"generic_result_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Generic Result Hash","type":"string"},"generic_selected_candidate_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Generic Selected Candidate Id","type":"string"},"remaining_uncertainties":{"items":{"type":"string"},"title":"Remaining Uncertainties","type":"array"}},"required":["decision_id","generic_selected_candidate_id","company_aware_selected_candidate_id","decisive_private_fact_ids","generic_result_hash","company_aware_result_hash","changed","explanation"],"title":"CounterfactualView","type":"object"}
```

### `CoverageBounds`

```json
{"additionalProperties":false,"properties":{"conservative":{"anyOf":[{"$ref":"#/components/schemas/ExactRatioView"},{"$ref":"#/components/schemas/BoundUnavailableView"}],"title":"Conservative"},"optimistic":{"anyOf":[{"$ref":"#/components/schemas/ExactRatioView"},{"$ref":"#/components/schemas/BoundUnavailableView"}],"title":"Optimistic"}},"required":["conservative","optimistic"],"title":"CoverageBounds","type":"object"}
```

### `CoverageProjection`

```json
{"additionalProperties":false,"properties":{"canonical_product_count":{"minimum":0.0,"title":"Canonical Product Count","type":"integer"},"duplicate_count":{"minimum":0.0,"title":"Duplicate Count","type":"integer"},"evaluated_solution_plan_count":{"minimum":0.0,"title":"Evaluated Solution Plan Count","type":"integer"},"excluded_count":{"minimum":0.0,"title":"Excluded Count","type":"integer"},"generated_solution_plan_count":{"minimum":0.0,"title":"Generated Solution Plan Count","type":"integer"},"product_evidence_option_count":{"minimum":0.0,"title":"Product Evidence Option Count","type":"integer"},"raw_record_count":{"minimum":0.0,"title":"Raw Record Count","type":"integer"},"statement":{"maxLength":500,"minLength":1,"title":"Statement","type":"string"}},"required":["raw_record_count","product_evidence_option_count","canonical_product_count","duplicate_count","generated_solution_plan_count","evaluated_solution_plan_count","excluded_count","statement"],"title":"CoverageProjection","type":"object"}
```

### `DecisionComponentResult`

```json
{"additionalProperties":false,"properties":{"component_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Component Id","type":"string"},"current_instance_id":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Current Instance Id"},"evidence_assessments":{"items":{"$ref":"#/components/schemas/EvidenceAssessmentView"},"title":"Evidence Assessments","type":"array"},"gate_results":{"items":{"$ref":"#/components/schemas/GateResultView"},"title":"Gate Results","type":"array"},"name":{"maxLength":200,"minLength":1,"title":"Name","type":"string"},"pack_id":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Pack Id"},"pack_version":{"anyOf":[{"minimum":1.0,"type":"integer"},{"type":"null"}],"title":"Pack Version"},"primary_reason":{"anyOf":[{"$ref":"#/components/schemas/GateReasonView"},{"type":"null"}]},"publisher_authority":{"anyOf":[{"$ref":"#/components/schemas/PackAuthority"},{"type":"null"}]},"status":{"$ref":"#/components/schemas/ComponentStatus"}},"required":["component_id","name","pack_id","pack_version","current_instance_id","publisher_authority","status","primary_reason","gate_results","evidence_assessments"],"title":"DecisionComponentResult","type":"object"}
```

### `DecisionIndexView`

```json
{"additionalProperties":false,"properties":{"active":{"items":{"$ref":"#/components/schemas/DecisionRequestView"},"title":"Active","type":"array"},"available_actions":{"items":{"$ref":"#/components/schemas/ActionDescriptor"},"title":"Available Actions","type":"array"},"history":{"items":{"$ref":"#/components/schemas/DecisionRequestView"},"title":"History","type":"array"}},"required":["active","history","available_actions"],"title":"DecisionIndexView","type":"object"}
```

### `DecisionLedgerV2`

```json
{"additionalProperties":false,"properties":{"company_profile_version":{"minimum":1.0,"title":"Company Profile Version","type":"integer"},"component_results":{"items":{"$ref":"#/components/schemas/DecisionComponentResult"},"title":"Component Results","type":"array"},"counterfactuals":{"items":{"$ref":"#/components/schemas/CounterfactualRecordView"},"minItems":1,"title":"Counterfactuals","type":"array"},"created_at":{"format":"date-time","title":"Created At","type":"string"},"decision_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Decision Hash","type":"string"},"decision_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Decision Id","type":"string"},"decision_outcome":{"$ref":"#/components/schemas/DecisionOutcome"},"decision_state":{"$ref":"#/components/schemas/DecisionVersionState"},"decision_version":{"minimum":1.0,"title":"Decision Version","type":"integer"},"evaluated_universe":{"$ref":"#/components/schemas/EvaluatedUniverseView"},"evaluation":{"$ref":"#/components/schemas/EvaluationRecord"},"policy_version":{"minimum":1.0,"title":"Policy Version","type":"integer"},"purchase_brief_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Purchase Brief Id","type":"string"},"purchase_brief_version":{"minimum":1.0,"title":"Purchase Brief Version","type":"integer"},"rank_stability":{"$ref":"#/components/schemas/RankStabilityProjection"},"request_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Request Id","type":"string"},"requirement_brief_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Requirement Brief Id","type":"string"},"requirement_brief_version":{"minimum":1.0,"title":"Requirement Brief Version","type":"integer"},"schema_version":{"pattern":"^[0-9]+\\.[0-9]+\\.[0-9]+$","title":"Schema Version","type":"string"},"selected_solution_plan_id":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Selected Solution Plan Id"},"solution_plans":{"items":{"$ref":"#/components/schemas/SolutionPlanRecord"},"minItems":1,"title":"Solution Plans","type":"array"},"stack_snapshot":{"minimum":1.0,"title":"Stack Snapshot","type":"integer"},"supersedes_decision_id":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Supersedes Decision Id"}},"required":["schema_version","decision_id","decision_version","decision_state","supersedes_decision_id","request_id","purchase_brief_id","purchase_brief_version","requirement_brief_id","requirement_brief_version","company_profile_version","stack_snapshot","policy_version","evaluation","evaluated_universe","component_results","solution_plans","decision_outcome","selected_solution_plan_id","rank_stability","counterfactuals","decision_hash","created_at"],"title":"DecisionLedgerV2","type":"object"}
```

### `DecisionOutcome`

```json
{"enum":["SELECTED_SOLUTION_PLAN","NO_ELIGIBLE_SUPPORTED_ACTION"],"title":"DecisionOutcome","type":"string"}
```

### `DecisionRequestCreate`

```json
{"additionalProperties":false,"properties":{"deadline":{"anyOf":[{"format":"date","type":"string"},{"type":"null"}],"title":"Deadline"},"desired_outcome":{"anyOf":[{"maxLength":1000,"type":"string"},{"type":"null"}],"title":"Desired Outcome"},"incumbent_instance_id":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Incumbent Instance Id"},"intent":{"maxLength":2000,"minLength":10,"title":"Intent","type":"string"},"mission_id":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Mission Id"},"scenario_id":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Scenario Id"},"visibility":{"$ref":"#/components/schemas/RequestVisibility","default":"SELECTIVE"}},"required":["intent"],"title":"DecisionRequestCreate","type":"object"}
```

### `DecisionRequestHeader`

```json
{"additionalProperties":false,"properties":{"decision_state":{"$ref":"#/components/schemas/DecisionVersionState"},"decision_version":{"minimum":1.0,"title":"Decision Version","type":"integer"},"evaluation_mode":{"const":"DEVELOPMENT_FIXTURE_NON_PRODUCTION","title":"Evaluation Mode","type":"string"},"fixture_label":{"const":"DEVELOPMENT_FIXTURE_NON_PRODUCTION","title":"Fixture Label","type":"string"},"id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Id","type":"string"},"intent":{"maxLength":500,"minLength":1,"title":"Intent","type":"string"},"scenario_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Scenario Id","type":"string"},"status":{"enum":["DRAFT","DISCOVERING","DECISION_READY","ACTION_IN_PROGRESS","RESULT_READY","COMPLETED"],"title":"Status","type":"string"},"superseded_by":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Superseded By"}},"required":["id","intent","status","decision_version","decision_state","evaluation_mode","scenario_id","fixture_label"],"title":"DecisionRequestHeader","type":"object"}
```

### `DecisionRequestView`

```json
{"additionalProperties":false,"properties":{"blocker":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Blocker"},"current_decision_version":{"anyOf":[{"minimum":1.0,"type":"integer"},{"type":"null"}],"title":"Current Decision Version"},"current_stage":{"$ref":"#/components/schemas/DecisionStage"},"deadline":{"anyOf":[{"format":"date","type":"string"},{"type":"null"}],"title":"Deadline"},"evaluation_mode":{"enum":["SCENARIO_SELECTION_REQUIRED","DEVELOPMENT_FIXTURE_NON_PRODUCTION","PROVIDER_CONFIGURATION_REQUIRED"],"title":"Evaluation Mode","type":"string"},"fixture_label":{"anyOf":[{"const":"DEVELOPMENT_FIXTURE_NON_PRODUCTION","type":"string"},{"type":"null"}],"title":"Fixture Label"},"href":{"title":"Href","type":"string"},"id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Id","type":"string"},"intent":{"title":"Intent","type":"string"},"last_checkpoint":{"title":"Last Checkpoint","type":"string"},"owner_role":{"$ref":"#/components/schemas/ActorRole"},"scenario_id":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Scenario Id"},"status":{"title":"Status","type":"string"},"visibility":{"$ref":"#/components/schemas/RequestVisibility"}},"required":["id","intent","status","visibility","owner_role","current_stage","last_checkpoint","evaluation_mode","href"],"title":"DecisionRequestView","type":"object"}
```

### `DecisionRuleItem`

```json
{"additionalProperties":false,"properties":{"id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Id","type":"string"},"kind":{"enum":["HARD_GATE","PREFERENCE","STACK_POLICY","APPROVAL"],"title":"Kind","type":"string"},"label":{"title":"Label","type":"string"},"required":{"title":"Required","type":"boolean"},"version":{"minimum":1.0,"title":"Version","type":"integer"},"weight":{"anyOf":[{"minimum":0.0,"type":"integer"},{"type":"null"}],"title":"Weight"}},"required":["id","kind","label","required","version"],"title":"DecisionRuleItem","type":"object"}
```

### `DecisionRulesView`

```json
{"additionalProperties":false,"properties":{"content_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Content Hash","type":"string"},"id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Id","type":"string"},"request_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Request Id","type":"string"},"rules":{"items":{"$ref":"#/components/schemas/DecisionRuleItem"},"title":"Rules","type":"array"},"version":{"minimum":1.0,"title":"Version","type":"integer"}},"required":["id","request_id","version","content_hash","rules"],"title":"DecisionRulesView","type":"object"}
```

### `DecisionSimulationCreate`

```json
{"additionalProperties":false,"properties":{"context_mode":{"default":"COMPANY_AWARE","enum":["COMPANY_AWARE","GENERIC_REQUEST_ONLY"],"title":"Context Mode","type":"string"},"preference_weight_overrides":{"patternProperties":{"^[a-z][a-z0-9_:-]{2,127}$":{"type":"integer"}},"propertyNames":{"maxLength":128,"minLength":3},"title":"Preference Weight Overrides","type":"object"},"reason":{"maxLength":1000,"minLength":3,"title":"Reason","type":"string"}},"required":["reason"],"title":"DecisionSimulationCreate","type":"object"}
```

### `DecisionSimulationView`

```json
{"additionalProperties":false,"properties":{"authoritative":{"const":false,"default":false,"title":"Authoritative","type":"boolean"},"baseline_solution_plan_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Baseline Solution Plan Id","type":"string"},"context_mode":{"enum":["COMPANY_AWARE","GENERIC_REQUEST_ONLY"],"title":"Context Mode","type":"string"},"decision_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Decision Id","type":"string"},"input_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Input Hash","type":"string"},"ranking_effect":{"const":false,"default":false,"title":"Ranking Effect","type":"boolean"},"result_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Result Hash","type":"string"},"simulated_order":{"items":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},"title":"Simulated Order","type":"array"},"simulated_solution_plan_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Simulated Solution Plan Id","type":"string"},"simulation_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Simulation Id","type":"string"}},"required":["simulation_id","decision_id","context_mode","baseline_solution_plan_id","simulated_solution_plan_id","simulated_order","input_hash","result_hash"],"title":"DecisionSimulationView","type":"object"}
```

### `DecisionStage`

```json
{"enum":["NEED","COMPANY_FIT","OPTIONS","ACTION","RESULT"],"title":"DecisionStage","type":"string"}
```

### `DecisionVersionState`

```json
{"enum":["CURRENT","SUPERSEDED"],"title":"DecisionVersionState","type":"string"}
```

### `DecisionView`

```json
{"additionalProperties":false,"properties":{"approval":{"anyOf":[{"$ref":"#/components/schemas/ApprovalProjection"},{"type":"null"}]},"company_context":{"$ref":"#/components/schemas/CompanyContextProjection"},"coverage":{"$ref":"#/components/schemas/CoverageProjection"},"decision_outcome":{"$ref":"#/components/schemas/DecisionOutcome"},"disclosure_preview":{"$ref":"#/components/schemas/DisclosurePreview"},"evaluation":{"$ref":"#/components/schemas/EvaluationSummary"},"payment_handoff":{"anyOf":[{"$ref":"#/components/schemas/PaymentHandoffProjection"},{"type":"null"}]},"rank_stability":{"$ref":"#/components/schemas/RankStabilityProjection"},"request":{"$ref":"#/components/schemas/DecisionRequestHeader"},"result_artifacts":{"items":{"$ref":"#/components/schemas/ResultArtifact"},"title":"Result Artifacts","type":"array"},"selected_action_plan":{"anyOf":[{"$ref":"#/components/schemas/SelectedActionPlan"},{"type":"null"}]},"solution_options":{"items":{"$ref":"#/components/schemas/SolutionOption"},"title":"Solution Options","type":"array"},"stack_change":{"anyOf":[{"$ref":"#/components/schemas/StackChangeProjection"},{"type":"null"}]},"workflow":{"$ref":"#/components/schemas/WorkflowProjection"}},"required":["request","workflow","evaluation","company_context","disclosure_preview","coverage","decision_outcome","rank_stability","solution_options","result_artifacts"],"title":"DecisionView","type":"object"}
```

### `DefaultComparison`

```json
{"additionalProperties":false,"properties":{"cost":{"$ref":"#/components/schemas/DefaultComparisonCost"},"next_action":{"maxLength":120,"minLength":1,"title":"Next Action","type":"string"},"stack_change":{"maxLength":500,"minLength":1,"title":"Stack Change","type":"string"}},"required":["cost","stack_change","next_action"],"title":"DefaultComparison","type":"object"}
```

### `DefaultComparisonCost`

```json
{"additionalProperties":false,"properties":{"amount":{"pattern":"^(0|[1-9][0-9]*)\\.[0-9]{2}$","title":"Amount","type":"string"},"currency":{"const":"USD","title":"Currency","type":"string"},"horizon_days":{"minimum":1.0,"title":"Horizon Days","type":"integer"}},"required":["amount","currency","horizon_days"],"title":"DefaultComparisonCost","type":"object"}
```

### `DisclosureDefaults`

```json
{"additionalProperties":false,"properties":{"allow_anonymized_requirement_preview":{"default":true,"title":"Allow Anonymized Requirement Preview","type":"boolean"},"allow_outcome_follow_up":{"default":true,"title":"Allow Outcome Follow Up","type":"boolean"},"share_organization_name_after_consent":{"default":false,"title":"Share Organization Name After Consent","type":"boolean"}},"title":"DisclosureDefaults","type":"object"}
```

### `DisclosurePreview`

```json
{"additionalProperties":false,"properties":{"exact_fields":{"items":{"type":"string"},"maxItems":32,"minItems":1,"title":"Exact Fields","type":"array"},"expires_at":{"format":"date-time","title":"Expires At","type":"string"},"omitted_categories":{"items":{"type":"string"},"maxItems":16,"minItems":1,"title":"Omitted Categories","type":"array"},"purpose":{"maxLength":240,"minLength":1,"title":"Purpose","type":"string"},"recipient":{"const":"SELLER","title":"Recipient","type":"string"},"source_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Source Hash","type":"string"},"source_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Source Id","type":"string"},"source_version":{"minimum":1.0,"title":"Source Version","type":"integer"},"status":{"enum":["ACTIVE","EXPIRED"],"title":"Status","type":"string"},"transformations":{"items":{"type":"string"},"maxItems":16,"title":"Transformations","type":"array"}},"required":["source_id","source_version","source_hash","recipient","purpose","exact_fields","transformations","omitted_categories","expires_at","status"],"title":"DisclosurePreview","type":"object"}
```

### `EngagementStatus`

```json
{"enum":["NOT_STARTED","SELLER_REVIEWING","SELLER_PASSED","OFFER_AVAILABLE","BUYER_CONSENT_PENDING","SELLER_CONSENT_PENDING","INTRODUCTION_READY","DECLINED","EXPIRED"],"title":"EngagementStatus","type":"string"}
```

### `EngagementView`

```json
{"additionalProperties":false,"properties":{"buyer_consented":{"title":"Buyer Consented","type":"boolean"},"contact_details":{"anyOf":[{"additionalProperties":{"type":"string"},"type":"object"},{"type":"null"}],"title":"Contact Details"},"id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Id","type":"string"},"seller_consented":{"title":"Seller Consented","type":"boolean"},"status":{"$ref":"#/components/schemas/EngagementStatus"}},"required":["id","status","buyer_consented","seller_consented"],"title":"EngagementView","type":"object"}
```

### `ErrorBody`

```json
{"additionalProperties":false,"properties":{"code":{"title":"Code","type":"string"},"details":{"additionalProperties":true,"title":"Details","type":"object"},"message":{"title":"Message","type":"string"},"next_action":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Next Action"},"request_id":{"title":"Request Id","type":"string"},"retryable":{"title":"Retryable","type":"boolean"}},"required":["code","message","request_id","retryable"],"title":"ErrorBody","type":"object"}
```

### `ErrorEnvelope`

```json
{"additionalProperties":false,"properties":{"error":{"$ref":"#/components/schemas/ErrorBody"}},"required":["error"],"title":"ErrorEnvelope","type":"object"}
```

### `EvaluatedUniverseView`

```json
{"additionalProperties":false,"properties":{"canonical_product_count":{"minimum":0.0,"title":"Canonical Product Count","type":"integer"},"coverage_statement":{"maxLength":500,"minLength":1,"title":"Coverage Statement","type":"string"},"duplicate_count":{"minimum":0.0,"title":"Duplicate Count","type":"integer"},"evaluated_solution_plan_count":{"minimum":0.0,"title":"Evaluated Solution Plan Count","type":"integer"},"excluded_count":{"minimum":0.0,"title":"Excluded Count","type":"integer"},"excluded_record_ids":{"items":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},"title":"Excluded Record Ids","type":"array"},"generated_solution_plan_count":{"minimum":0.0,"title":"Generated Solution Plan Count","type":"integer"},"identity_merges":{"items":{"$ref":"#/components/schemas/IdentityMergeView"},"title":"Identity Merges","type":"array"},"included_record_ids":{"items":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},"title":"Included Record Ids","type":"array"},"product_evidence_option_count":{"minimum":0.0,"title":"Product Evidence Option Count","type":"integer"},"raw_record_count":{"minimum":0.0,"title":"Raw Record Count","type":"integer"}},"required":["raw_record_count","product_evidence_option_count","canonical_product_count","duplicate_count","generated_solution_plan_count","evaluated_solution_plan_count","excluded_count","included_record_ids","excluded_record_ids","identity_merges","coverage_statement"],"title":"EvaluatedUniverseView","type":"object"}
```

### `EvaluationRecord`

```json
{"additionalProperties":false,"properties":{"bound_unavailable_plan_ids":{"items":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},"title":"Bound Unavailable Plan Ids","type":"array"},"evaluated_at":{"format":"date-time","title":"Evaluated At","type":"string"},"evaluation_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Evaluation Id","type":"string"},"evaluation_payload_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Evaluation Payload Hash","type":"string"},"frozen_versions":{"$ref":"#/components/schemas/FrozenVersions"},"ordering_frontier_plan_ids":{"items":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},"title":"Ordering Frontier Plan Ids","type":"array"},"ranked_solution_plan_ids":{"items":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},"title":"Ranked Solution Plan Ids","type":"array"}},"required":["evaluation_id","evaluated_at","evaluation_payload_hash","frozen_versions","ranked_solution_plan_ids","ordering_frontier_plan_ids","bound_unavailable_plan_ids"],"title":"EvaluationRecord","type":"object"}
```

### `EvaluationReplayView`

```json
{"additionalProperties":false,"properties":{"byte_stable":{"title":"Byte Stable","type":"boolean"},"counterfactual_matches":{"title":"Counterfactual Matches","type":"boolean"},"decision_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Decision Id","type":"string"},"evaluation_run_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Evaluation Run Id","type":"string"},"ordering_matches":{"title":"Ordering Matches","type":"boolean"},"replayed_decision_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Replayed Decision Hash","type":"string"},"statuses_match":{"title":"Statuses Match","type":"boolean"},"stored_decision_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Stored Decision Hash","type":"string"}},"required":["evaluation_run_id","decision_id","stored_decision_hash","replayed_decision_hash","ordering_matches","statuses_match","counterfactual_matches","byte_stable"],"title":"EvaluationReplayView","type":"object"}
```

### `EvaluationSummary`

```json
{"additionalProperties":false,"properties":{"decision_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Decision Hash","type":"string"},"engine_version":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Engine Version","type":"string"},"id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Id","type":"string"},"payload_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Payload Hash","type":"string"},"pipeline_version":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Pipeline Version","type":"string"}},"required":["id","payload_hash","decision_hash","pipeline_version","engine_version"],"title":"EvaluationSummary","type":"object"}
```

### `EvidenceAgeBounds`

```json
{"additionalProperties":false,"properties":{"lower":{"anyOf":[{"$ref":"#/components/schemas/ExactRatioView"},{"$ref":"#/components/schemas/BoundUnavailableView"}],"title":"Lower"},"upper":{"anyOf":[{"$ref":"#/components/schemas/ExactRatioView"},{"$ref":"#/components/schemas/BoundUnavailableView"}],"title":"Upper"}},"required":["lower","upper"],"title":"EvidenceAgeBounds","type":"object"}
```

### `EvidenceAssessmentView`

```json
{"additionalProperties":false,"properties":{"age_bounds":{"anyOf":[{"$ref":"#/components/schemas/EvidenceAgeBounds"},{"type":"null"}]},"disputed":{"title":"Disputed","type":"boolean"},"evidence_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Evidence Id","type":"string"},"field":{"pattern":"^[a-z][a-z0-9_.]{2,127}$","title":"Field","type":"string"},"freshness_current":{"anyOf":[{"type":"boolean"},{"type":"null"}],"title":"Freshness Current"},"reasons":{"items":{"type":"string"},"title":"Reasons","type":"array"},"reconstructable":{"title":"Reconstructable","type":"boolean"},"record_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Record Id","type":"string"},"revoked":{"title":"Revoked","type":"boolean"},"scope_match":{"title":"Scope Match","type":"boolean"},"source_class":{"maxLength":100,"minLength":1,"title":"Source Class","type":"string"},"state":{"enum":["ACCEPTABLE","UNKNOWN","STALE","CONFLICT"],"title":"State","type":"string"},"verification_method":{"maxLength":100,"minLength":1,"title":"Verification Method","type":"string"}},"required":["evidence_id","record_id","field","source_class","verification_method","scope_match","reconstructable","freshness_current","disputed","revoked","state","reasons","age_bounds"],"title":"EvidenceAssessmentView","type":"object"}
```

### `EvidenceCoverageView`

```json
{"additionalProperties":false,"properties":{"decision_material":{"$ref":"#/components/schemas/CoverageBounds"},"hard":{"$ref":"#/components/schemas/ExactRatioView"}},"required":["hard","decision_material"],"title":"EvidenceCoverageView","type":"object"}
```

### `EvidenceFrontierItem`

```json
{"additionalProperties":false,"properties":{"criterion_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Criterion Id","type":"string"},"option_ids":{"items":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},"minItems":1,"title":"Option Ids","type":"array"},"permitted_resolution":{"anyOf":[{"maxLength":300,"type":"string"},{"type":"null"}],"title":"Permitted Resolution"},"reason_code":{"pattern":"^[A-Z][A-Z0-9_]{2,63}$","title":"Reason Code","type":"string"}},"required":["criterion_id","reason_code","option_ids"],"title":"EvidenceFrontierItem","type":"object"}
```

### `EvidenceSummary`

```json
{"additionalProperties":false,"properties":{"href":{"maxLength":500,"pattern":"^/","title":"Href","type":"string"},"id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Id","type":"string"},"label":{"maxLength":200,"minLength":1,"title":"Label","type":"string"},"publisher_authority":{"$ref":"#/components/schemas/PackAuthority"},"verification_state":{"enum":["VERIFIED","SELLER_ASSERTED","STALE","INSUFFICIENT","CONFLICTING","REVOKED"],"title":"Verification State","type":"string"}},"required":["id","label","publisher_authority","verification_state","href"],"title":"EvidenceSummary","type":"object"}
```

### `ExactRatioView`

```json
{"additionalProperties":false,"properties":{"denominator":{"exclusiveMinimum":0.0,"title":"Denominator","type":"integer"},"numerator":{"minimum":0.0,"title":"Numerator","type":"integer"}},"required":["numerator","denominator"],"title":"ExactRatioView","type":"object"}
```

### `ExactScoreView`

```json
{"additionalProperties":false,"properties":{"denominator":{"exclusiveMinimum":0.0,"title":"Denominator","type":"integer"},"display":{"pattern":"^(0|[1-9][0-9]*)\\.[0-9]{2}$","title":"Display","type":"string"},"numerator":{"minimum":0.0,"title":"Numerator","type":"integer"}},"required":["numerator","denominator","display"],"title":"ExactScoreView","type":"object"}
```

### `ExchangeCaseCreate`

```json
{"additionalProperties":false,"properties":{"candidate_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Candidate Id","type":"string"},"purchase_request_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Purchase Request Id","type":"string"}},"required":["purchase_request_id","candidate_id"],"title":"ExchangeCaseCreate","type":"object"}
```

### `ExchangeCaseCreated`

```json
{"additionalProperties":false,"properties":{"case_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Case Id","type":"string"},"expires_at":{"format":"date-time","title":"Expires At","type":"string"},"projection":{"$ref":"#/components/schemas/ExchangeProjectionView"},"route_capability":{"maxLength":4096,"minLength":64,"title":"Route Capability","type":"string"}},"required":["case_id","route_capability","expires_at","projection"],"title":"ExchangeCaseCreated","type":"object"}
```

### `ExchangeEvidencePublish`

```json
{"additionalProperties":false,"properties":{"expected_version":{"minimum":1.0,"title":"Expected Version","type":"integer"},"published_span_ids":{"items":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},"maxItems":64,"title":"Published Span Ids","type":"array"},"summary":{"maxLength":500,"minLength":1,"title":"Summary","type":"string"}},"required":["expected_version","summary"],"title":"ExchangeEvidencePublish","type":"object"}
```

### `ExchangeHandoffCreate`

```json
{"additionalProperties":false,"properties":{"expected_version":{"minimum":1.0,"title":"Expected Version","type":"integer"},"offer_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Offer Hash","type":"string"}},"required":["expected_version","offer_hash"],"title":"ExchangeHandoffCreate","type":"object"}
```

### `ExchangeHandoffOpen`

```json
{"additionalProperties":false,"properties":{"handoff_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Handoff Hash","type":"string"}},"required":["handoff_hash"],"title":"ExchangeHandoffOpen","type":"object"}
```

### `ExchangeHandoffView`

```json
{"additionalProperties":false,"properties":{"amount":{"pattern":"^(?!^[-+.]*$)[+-]?0*(?:\\d{0,18}|(?=[\\d.]{1,21}0*$)\\d{0,18}\\.\\d{0,2}0*$)","title":"Amount","type":"string"},"approval_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Approval Hash","type":"string"},"case_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Case Id","type":"string"},"currency":{"pattern":"^[A-Z]{3}$","title":"Currency","type":"string"},"destination_url":{"maxLength":2000,"pattern":"^https://","title":"Destination Url","type":"string"},"expires_at":{"format":"date-time","title":"Expires At","type":"string"},"handoff_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Handoff Hash","type":"string"},"id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Id","type":"string"},"offer_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Offer Hash","type":"string"},"opened_at":{"anyOf":[{"format":"date-time","type":"string"},{"type":"null"}],"title":"Opened At"},"recipient":{"maxLength":200,"minLength":1,"title":"Recipient","type":"string"},"reference":{"maxLength":160,"minLength":1,"title":"Reference","type":"string"},"status":{"enum":["READY","OPENED","EXPIRED","CANCELLED"],"title":"Status","type":"string"}},"required":["id","case_id","offer_hash","approval_hash","handoff_hash","destination_url","recipient","amount","currency","reference","status","expires_at"],"title":"ExchangeHandoffView","type":"object"}
```

### `ExchangeOfferAccept`

```json
{"additionalProperties":false,"properties":{"expected_version":{"minimum":1.0,"title":"Expected Version","type":"integer"},"offer_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Offer Hash","type":"string"}},"required":["expected_version","offer_hash"],"title":"ExchangeOfferAccept","type":"object"}
```

### `ExchangeOfferApprove`

```json
{"additionalProperties":false,"properties":{"approval_expires_at":{"format":"date-time","title":"Approval Expires At","type":"string"},"expected_version":{"minimum":1.0,"title":"Expected Version","type":"integer"},"offer_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Offer Hash","type":"string"}},"required":["expected_version","offer_hash","approval_expires_at"],"title":"ExchangeOfferApprove","type":"object"}
```

### `ExchangeOfferCreate`

```json
{"additionalProperties":false,"properties":{"changed_terms":{"items":{"type":"string"},"maxItems":16,"title":"Changed Terms","type":"array"},"currency":{"pattern":"^[A-Z]{3}$","title":"Currency","type":"string"},"expected_version":{"minimum":1.0,"title":"Expected Version","type":"integer"},"expires_at":{"format":"date-time","title":"Expires At","type":"string"},"lines":{"items":{"$ref":"#/components/schemas/ExchangeOfferLineInput"},"maxItems":100,"minItems":1,"title":"Lines","type":"array"},"rationale":{"maxLength":1000,"minLength":1,"title":"Rationale","type":"string"},"total":{"anyOf":[{"minimum":0.0,"type":"number"},{"pattern":"^(?!^[-+.]*$)[+-]?0*(?:\\d{0,18}|(?=[\\d.]{1,21}0*$)\\d{0,18}\\.\\d{0,2}0*$)","type":"string"}],"title":"Total"}},"required":["expected_version","currency","lines","total","rationale","expires_at"],"title":"ExchangeOfferCreate","type":"object"}
```

### `ExchangeOfferLineInput`

```json
{"additionalProperties":false,"properties":{"description":{"maxLength":240,"minLength":1,"title":"Description","type":"string"},"item_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Item Id","type":"string"},"quantity":{"maximum":1000000.0,"minimum":1.0,"title":"Quantity","type":"integer"},"unit_price":{"anyOf":[{"minimum":0.0,"type":"number"},{"pattern":"^(?!^[-+.]*$)[+-]?0*(?:\\d{0,18}|(?=[\\d.]{1,21}0*$)\\d{0,18}\\.\\d{0,2}0*$)","type":"string"}],"title":"Unit Price"}},"required":["item_id","description","quantity","unit_price"],"title":"ExchangeOfferLineInput","type":"object"}
```

### `ExchangeProjectionView`

```json
{"additionalProperties":false,"properties":{"case_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Case Id","type":"string"},"party":{"enum":["BUYER","SELLER"],"title":"Party","type":"string"},"projection_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Projection Hash","type":"string"},"released":{"additionalProperties":true,"title":"Released","type":"object"},"state":{"enum":["CREATED","REQUIREMENT_RELEASED","EVIDENCE_RELEASED","OFFERED","COUNTERED","AGREED_PENDING_APPROVAL","APPROVED_FOR_HANDOFF","REJECTED","EXPIRED"],"title":"State","type":"string"},"version":{"minimum":1.0,"title":"Version","type":"integer"}},"required":["case_id","party","state","version","released","projection_hash"],"title":"ExchangeProjectionView","type":"object"}
```

### `ExecutionStep`

```json
{"additionalProperties":false,"properties":{"artifact_id":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Artifact Id"},"available_action":{"anyOf":[{"$ref":"#/components/schemas/ActionDescriptor"},{"type":"null"}]},"blocker":{"anyOf":[{"maxLength":300,"type":"string"},{"type":"null"}],"title":"Blocker"},"checkpoint_id":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Checkpoint Id"},"completed_at":{"anyOf":[{"format":"date-time","type":"string"},{"type":"null"}],"title":"Completed At"},"id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Id","type":"string"},"owner_role":{"$ref":"#/components/schemas/ActorRole"},"started_at":{"anyOf":[{"format":"date-time","type":"string"},{"type":"null"}],"title":"Started At"},"status":{"$ref":"#/components/schemas/ExecutionStepStatus"},"type":{"$ref":"#/components/schemas/ExecutionStepType"}},"required":["id","type","status","owner_role"],"title":"ExecutionStep","type":"object"}
```

### `ExecutionStepStatus`

```json
{"enum":["NOT_REACHED","AVAILABLE","CURRENT","BLOCKED","COMPLETED","SKIPPED","FAILED_RETRYABLE","FAILED_FINAL"],"title":"ExecutionStepStatus","type":"string"}
```

### `ExecutionStepType`

```json
{"enum":["REVIEW","REQUIRED_AUTHORITY","EXECUTE_OR_ASSIGN","VERIFY"],"title":"ExecutionStepType","type":"string"}
```

### `FrozenVersions`

```json
{"additionalProperties":false,"properties":{"company_profile":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Company Profile","type":"string"},"engine":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Engine","type":"string"},"fx":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Fx","type":"string"},"normalization":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Normalization","type":"string"},"offer_set":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Offer Set","type":"string"},"pack_set":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Pack Set","type":"string"},"pipeline":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Pipeline","type":"string"},"policy":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Policy","type":"string"},"registry":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Registry","type":"string"},"request":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Request","type":"string"},"stackfile":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Stackfile","type":"string"},"taxonomy":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Taxonomy","type":"string"}},"required":["request","company_profile","stackfile","registry","pack_set","offer_set","taxonomy","normalization","policy","fx","pipeline","engine"],"title":"FrozenVersions","type":"object"}
```

### `GateReasonView`

```json
{"additionalProperties":false,"properties":{"detail":{"maxLength":500,"minLength":1,"title":"Detail","type":"string"},"reason_code":{"pattern":"^[A-Z][A-Z0-9_]{2,63}$","title":"Reason Code","type":"string"},"status":{"$ref":"#/components/schemas/ComponentStatus"}},"required":["reason_code","status","detail"],"title":"GateReasonView","type":"object"}
```

### `GateResultView`

```json
{"additionalProperties":false,"properties":{"evaluated_predicates":{"items":{"type":"string"},"title":"Evaluated Predicates","type":"array"},"gate_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Gate Id","type":"string"},"permitted_resolution":{"anyOf":[{"maxLength":300,"type":"string"},{"type":"null"}],"title":"Permitted Resolution"},"reasons":{"items":{"$ref":"#/components/schemas/GateReasonView"},"title":"Reasons","type":"array"},"truth":{"$ref":"#/components/schemas/TruthValue"}},"required":["gate_id","truth","reasons","evaluated_predicates","permitted_resolution"],"title":"GateResultView","type":"object"}
```

### `HealthResponse`

```json
{"additionalProperties":false,"properties":{"agent_runtime":{"enum":["ready","unavailable","not_checked"],"title":"Agent Runtime","type":"string"},"database":{"enum":["configured","unavailable","not_checked"],"title":"Database","type":"string"},"fixture_mode":{"title":"Fixture Mode","type":"boolean"},"service":{"const":"sira-api","default":"sira-api","title":"Service","type":"string"},"status":{"enum":["ok","degraded"],"title":"Status","type":"string"},"version":{"title":"Version","type":"string"}},"required":["status","version","database","agent_runtime","fixture_mode"],"title":"HealthResponse","type":"object"}
```

### `IdentityMergeView`

```json
{"additionalProperties":false,"properties":{"canonical_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Canonical Id","type":"string"},"merged_record_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Merged Record Id","type":"string"},"reasons":{"items":{"type":"string"},"minItems":1,"title":"Reasons","type":"array"}},"required":["canonical_id","merged_record_id","reasons"],"title":"IdentityMergeView","type":"object"}
```

### `MerchantProjection`

```json
{"additionalProperties":false,"properties":{"candidate_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Candidate Id","type":"string"},"id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Id","type":"string"},"offer_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Offer Id","type":"string"}},"required":["id","offer_id","candidate_id"],"title":"MerchantProjection","type":"object"}
```

### `MissionArtifactView`

```json
{"properties":{"authority":{"title":"Authority","type":"string"},"id":{"title":"Id","type":"string"},"kind":{"title":"Kind","type":"string"},"payload":{"additionalProperties":true,"title":"Payload","type":"object"},"source_refs":{"items":{"additionalProperties":true,"type":"object"},"title":"Source Refs","type":"array"},"status":{"default":"READY","title":"Status","type":"string"},"title":{"title":"Title","type":"string"}},"required":["id","kind","title","authority","payload"],"title":"MissionArtifactView","type":"object"}
```

### `MissionEventView`

```json
{"properties":{"details":{"additionalProperties":true,"title":"Details","type":"object"},"id":{"title":"Id","type":"string"},"occurred_at":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Occurred At"},"sequence":{"title":"Sequence","type":"integer"},"summary":{"title":"Summary","type":"string"},"type":{"title":"Type","type":"string"},"verified":{"default":false,"title":"Verified","type":"boolean"}},"required":["id","sequence","type","summary"],"title":"MissionEventView","type":"object"}
```

### `MissionSnapshotView`

```json
{"properties":{"artifacts":{"items":{"$ref":"#/components/schemas/MissionArtifactView"},"title":"Artifacts","type":"array"},"events":{"items":{"$ref":"#/components/schemas/MissionEventView"},"title":"Events","type":"array"},"handoffs":{"items":{"additionalProperties":true,"type":"object"},"title":"Handoffs","type":"array"},"mission":{"$ref":"#/components/schemas/MissionSummaryView"},"open_tasks":{"items":{"additionalProperties":true,"type":"object"},"title":"Open Tasks","type":"array"}},"required":["mission","events","artifacts"],"title":"MissionSnapshotView","type":"object"}
```

### `MissionSummaryView`

```json
{"properties":{"goal":{"title":"Goal","type":"string"},"id":{"title":"Id","type":"string"},"mode":{"enum":["sira","seil"],"title":"Mode","type":"string"},"plan":{"items":{"additionalProperties":true,"type":"object"},"title":"Plan","type":"array"},"state":{"title":"State","type":"string"},"stop_reason":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Stop Reason"},"version":{"title":"Version","type":"integer"}},"required":["id","mode","goal","state","version"],"title":"MissionSummaryView","type":"object"}
```

### `MoneyViewV2`

```json
{"additionalProperties":false,"properties":{"amount":{"pattern":"^(0|[1-9][0-9]*)\\.[0-9]{2}$","title":"Amount","type":"string"},"currency":{"const":"USD","title":"Currency","type":"string"}},"required":["amount","currency"],"title":"MoneyViewV2","type":"object"}
```

### `NotificationChannels`

```json
{"additionalProperties":false,"properties":{"email":{"default":false,"title":"Email","type":"boolean"},"in_app":{"default":true,"title":"In App","type":"boolean"}},"title":"NotificationChannels","type":"object"}
```

### `OperationStatus`

```json
{"enum":["QUEUED","RUNNING","WAITING_FOR_HUMAN","RETRYABLE_ERROR","UNCERTAIN","COMPLETED","FAILED_FINAL"],"title":"OperationStatus","type":"string"}
```

### `OptionFeedbackAction`

```json
{"enum":["KEEP_FOR_COMPARISON","ELIMINATE","ASK_VENDOR","SAVE","NEED_EVIDENCE"],"title":"OptionFeedbackAction","type":"string"}
```

### `OptionFeedbackCreate`

```json
{"additionalProperties":false,"properties":{"action":{"$ref":"#/components/schemas/OptionFeedbackAction"},"proposed_criterion_change":{"anyOf":[{"patternProperties":{"^[a-z][a-z0-9_:-]{2,127}$":{"type":"integer"}},"propertyNames":{"maxLength":128,"minLength":3},"type":"object"},{"type":"null"}],"title":"Proposed Criterion Change"},"reason":{"maxLength":1000,"minLength":3,"title":"Reason","type":"string"}},"required":["action","reason"],"title":"OptionFeedbackCreate","type":"object"}
```

### `OptionFeedbackView`

```json
{"additionalProperties":false,"properties":{"action":{"$ref":"#/components/schemas/OptionFeedbackAction"},"contact_details_revealed":{"const":false,"default":false,"title":"Contact Details Revealed","type":"boolean"},"engagement_id":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Engagement Id"},"id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Id","type":"string"},"proposal_id":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Proposal Id"},"ranking_effect":{"const":false,"default":false,"title":"Ranking Effect","type":"boolean"},"reason":{"title":"Reason","type":"string"},"request_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Request Id","type":"string"},"solution_plan_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Solution Plan Id","type":"string"}},"required":["id","request_id","solution_plan_id","action","reason"],"title":"OptionFeedbackView","type":"object"}
```

### `OutcomeCheckpointCreate`

```json
{"additionalProperties":false,"properties":{"metric":{"maxLength":200,"minLength":1,"title":"Metric","type":"string"},"observed_at":{"format":"date-time","title":"Observed At","type":"string"},"observed_value":{"pattern":"^-?(0|[1-9][0-9]*)(\\.[0-9]{1,6})?$","title":"Observed Value","type":"string"},"source_class":{"enum":["SYSTEM_OBSERVATION","HUMAN_ATTESTATION","PROVIDER_REPORT"],"title":"Source Class","type":"string"},"source_reference":{"maxLength":500,"minLength":3,"title":"Source Reference","type":"string"}},"required":["metric","observed_value","observed_at","source_class","source_reference"],"title":"OutcomeCheckpointCreate","type":"object"}
```

### `OutcomeCheckpointView`

```json
{"additionalProperties":false,"properties":{"checkpoint_days":{"maximum":365.0,"minimum":1.0,"title":"Checkpoint Days","type":"integer"},"checkpoint_due_at":{"format":"date-time","title":"Checkpoint Due At","type":"string"},"checkpoint_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Checkpoint Hash","type":"string"},"decision_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Decision Hash","type":"string"},"decision_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Decision Id","type":"string"},"id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Id","type":"string"},"measurement_started_at":{"format":"date-time","title":"Measurement Started At","type":"string"},"metric":{"title":"Metric","type":"string"},"observed_at":{"format":"date-time","title":"Observed At","type":"string"},"observed_value":{"pattern":"^-?(0|[1-9][0-9]*)(\\.[0-9]{1,6})?$","title":"Observed Value","type":"string"},"preference_proposal":{"anyOf":[{"additionalProperties":true,"type":"object"},{"type":"null"}],"title":"Preference Proposal"},"purchase_intent_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Purchase Intent Id","type":"string"},"solution_plan_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Solution Plan Id","type":"string"},"source_class":{"enum":["SYSTEM_OBSERVATION","HUMAN_ATTESTATION","PROVIDER_REPORT"],"title":"Source Class","type":"string"},"source_reference_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Source Reference Hash","type":"string"},"state":{"enum":["MEASURING","ACHIEVED","NOT_ACHIEVED","INCONCLUSIVE"],"title":"State","type":"string"},"target_operator":{"enum":["gte","lte"],"title":"Target Operator","type":"string"},"target_value":{"pattern":"^-?(0|[1-9][0-9]*)(\\.[0-9]{1,6})?$","title":"Target Value","type":"string"}},"required":["id","purchase_intent_id","decision_id","decision_hash","solution_plan_id","metric","target_value","target_operator","observed_value","checkpoint_days","measurement_started_at","checkpoint_due_at","observed_at","state","source_class","source_reference_hash","checkpoint_hash"],"title":"OutcomeCheckpointView","type":"object"}
```

### `PackAuthority`

```json
{"enum":["SELLER_SEALED","PLATFORM_COMPILED","EXTERNAL_UNSEALED"],"title":"PackAuthority","type":"string"}
```

### `PaymentHandoffProjection`

```json
{"additionalProperties":false,"properties":{"amount":{"pattern":"^(0|[1-9][0-9]*)\\.[0-9]{2}$","title":"Amount","type":"string"},"approval_request_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Approval Request Id","type":"string"},"currency":{"pattern":"^[A-Z]{3}$","title":"Currency","type":"string"},"destination_url":{"maxLength":2000,"pattern":"^https://","title":"Destination Url","type":"string"},"expires_at":{"format":"date-time","title":"Expires At","type":"string"},"handoff_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Handoff Hash","type":"string"},"href":{"maxLength":500,"minLength":1,"title":"Href","type":"string"},"id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Id","type":"string"},"intent_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Intent Hash","type":"string"},"opened_at":{"anyOf":[{"format":"date-time","type":"string"},{"type":"null"}],"title":"Opened At"},"purchase_intent_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Purchase Intent Id","type":"string"},"recipient":{"maxLength":200,"minLength":1,"title":"Recipient","type":"string"},"reference":{"maxLength":160,"minLength":1,"title":"Reference","type":"string"},"status":{"enum":["READY","OPENED","EXPIRED","CANCELLED"],"title":"Status","type":"string"}},"required":["id","purchase_intent_id","approval_request_id","intent_hash","handoff_hash","destination_url","recipient","amount","currency","reference","status","expires_at","href"],"title":"PaymentHandoffProjection","type":"object"}
```

### `PaymentHandoffView`

```json
{"additionalProperties":false,"properties":{"amount":{"pattern":"^(0|[1-9][0-9]*)\\.[0-9]{2}$","title":"Amount","type":"string"},"approval_request_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Approval Request Id","type":"string"},"currency":{"pattern":"^[A-Z]{3}$","title":"Currency","type":"string"},"destination_url":{"maxLength":2000,"pattern":"^https://","title":"Destination Url","type":"string"},"expires_at":{"format":"date-time","title":"Expires At","type":"string"},"handoff_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Handoff Hash","type":"string"},"id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Id","type":"string"},"intent_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Intent Hash","type":"string"},"opened_at":{"anyOf":[{"format":"date-time","type":"string"},{"type":"null"}],"title":"Opened At"},"purchase_intent_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Purchase Intent Id","type":"string"},"recipient":{"maxLength":200,"minLength":1,"title":"Recipient","type":"string"},"reference":{"maxLength":160,"minLength":1,"title":"Reference","type":"string"},"status":{"enum":["READY","OPENED","EXPIRED","CANCELLED"],"title":"Status","type":"string"}},"required":["id","purchase_intent_id","approval_request_id","intent_hash","handoff_hash","destination_url","recipient","amount","currency","reference","status","expires_at"],"title":"PaymentHandoffView","type":"object"}
```

### `PlanComponentView`

```json
{"additionalProperties":false,"properties":{"action_type":{"$ref":"#/components/schemas/SolutionActionType"},"component_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Component Id","type":"string"},"source_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Source Id","type":"string"},"source_type":{"enum":["PRODUCT_EVIDENCE","CURRENT_INSTANCE","CONTRACT","DEPENDENCY"],"title":"Source Type","type":"string"}},"required":["component_id","source_type","source_id","action_type"],"title":"PlanComponentView","type":"object"}
```

### `PlanDimensionsView`

```json
{"additionalProperties":false,"properties":{"bound_unavailable_reasons":{"items":{"type":"string"},"title":"Bound Unavailable Reasons","type":"array"},"conflicting_count":{"minimum":0.0,"title":"Conflicting Count","type":"integer"},"cost_line_items":{"items":{"$ref":"#/components/schemas/CostLineItemBoundsView"},"title":"Cost Line Items","type":"array"},"decision_material_coverage":{"$ref":"#/components/schemas/CoverageBounds"},"hard_coverage":{"$ref":"#/components/schemas/ExactRatioView"},"maximum_evidence_age_ratio":{"$ref":"#/components/schemas/EvidenceAgeBounds"},"payment_required":{"title":"Payment Required","type":"boolean"},"preference":{"$ref":"#/components/schemas/PreferenceScoreBounds"},"stack_risk":{"$ref":"#/components/schemas/StackRiskBounds"},"total_cost":{"$ref":"#/components/schemas/TotalCostBounds"},"universe_coverage":{"$ref":"#/components/schemas/ExactRatioView"},"unresolved_count":{"minimum":0.0,"title":"Unresolved Count","type":"integer"}},"required":["preference","stack_risk","total_cost","cost_line_items","payment_required","hard_coverage","decision_material_coverage","maximum_evidence_age_ratio","universe_coverage","unresolved_count","conflicting_count","bound_unavailable_reasons"],"title":"PlanDimensionsView","type":"object"}
```

### `PlanSelectionCreate`

```json
{"additionalProperties":false,"properties":{"decision_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Decision Hash","type":"string"},"decision_version":{"minimum":1.0,"title":"Decision Version","type":"integer"},"solution_plan_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Solution Plan Id","type":"string"}},"required":["solution_plan_id","decision_version","decision_hash"],"title":"PlanSelectionCreate","type":"object"}
```

### `PlanSelectionState`

```json
{"enum":["SELECTED","SUPERSEDED","CANCELLED"],"title":"PlanSelectionState","type":"string"}
```

### `PlanSelectionView`

```json
{"additionalProperties":false,"properties":{"action_run_href":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Action Run Href"},"decision_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Decision Hash","type":"string"},"decision_version":{"minimum":1.0,"title":"Decision Version","type":"integer"},"selected_decision_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Selected Decision Id","type":"string"},"selection_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Selection Id","type":"string"},"solution_plan_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Solution Plan Id","type":"string"},"source_decision_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Source Decision Id","type":"string"},"state":{"$ref":"#/components/schemas/PlanSelectionState"}},"required":["selection_id","source_decision_id","selected_decision_id","solution_plan_id","decision_version","decision_hash","state"],"title":"PlanSelectionView","type":"object"}
```

### `PreferenceScoreBounds`

```json
{"additionalProperties":false,"properties":{"conservative":{"$ref":"#/components/schemas/ExactScoreView"},"optimistic":{"$ref":"#/components/schemas/ExactScoreView"}},"required":["conservative","optimistic"],"title":"PreferenceScoreBounds","type":"object"}
```

### `ProductEvidenceComponent`

```json
{"additionalProperties":false,"properties":{"action":{"enum":["ADD","REMOVE","RETAIN","CONFIGURE","RENEW","RESIZE","CANCEL","REUSE"],"title":"Action","type":"string"},"current_instance_id":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Current Instance Id"},"product_evidence_id":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Product Evidence Id"},"publisher_authority":{"anyOf":[{"$ref":"#/components/schemas/PackAuthority"},{"type":"null"}]},"verification_summary":{"maxLength":300,"minLength":1,"title":"Verification Summary","type":"string"}},"required":["product_evidence_id","current_instance_id","action","publisher_authority","verification_summary"],"title":"ProductEvidenceComponent","type":"object"}
```

### `ProposalDecisionCreate`

```json
{"additionalProperties":false,"properties":{"reason":{"maxLength":1000,"minLength":3,"title":"Reason","type":"string"}},"required":["reason"],"title":"ProposalDecisionCreate","type":"object"}
```

### `ProposalDecisionView`

```json
{"additionalProperties":false,"properties":{"base_purchase_brief_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Base Purchase Brief Id","type":"string"},"proposal_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Proposal Id","type":"string"},"ranking_effect":{"title":"Ranking Effect","type":"boolean"},"resulting_decision_hash":{"anyOf":[{"pattern":"^sha256:[0-9a-f]{64}$","type":"string"},{"type":"null"}],"title":"Resulting Decision Hash"},"resulting_decision_id":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Resulting Decision Id"},"resulting_decision_version":{"anyOf":[{"type":"integer"},{"type":"null"}],"title":"Resulting Decision Version"},"resulting_purchase_brief_id":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Resulting Purchase Brief Id"},"resulting_version":{"anyOf":[{"type":"integer"},{"type":"null"}],"title":"Resulting Version"},"status":{"enum":["ACCEPTED","REJECTED"],"title":"Status","type":"string"}},"required":["proposal_id","base_purchase_brief_id","status","ranking_effect"],"title":"ProposalDecisionView","type":"object"}
```

### `PublicMarketplaceProductView`

```json
{"additionalProperties":false,"properties":{"product":{"additionalProperties":true,"title":"Product","type":"object"}},"required":["product"],"title":"PublicMarketplaceProductView","type":"object"}
```

### `PublicMarketplaceSearchView`

```json
{"additionalProperties":false,"properties":{"category":{"title":"Category","type":"string"},"query_model_id":{"title":"Query Model Id","type":"string"},"results":{"items":{"additionalProperties":true,"type":"object"},"title":"Results","type":"array"}},"required":["category","query_model_id","results"],"title":"PublicMarketplaceSearchView","type":"object"}
```

### `PublisherAuthorityProjection`

```json
{"additionalProperties":false,"properties":{"label":{"maxLength":100,"minLength":1,"title":"Label","type":"string"},"supporting_copy":{"maxLength":500,"minLength":1,"title":"Supporting Copy","type":"string"},"value":{"$ref":"#/components/schemas/PackAuthority"}},"required":["value","label","supporting_copy"],"title":"PublisherAuthorityProjection","type":"object"}
```

### `PurchaseIntentCreate`

```json
{"additionalProperties":false,"properties":{"solution_plan_id":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Solution Plan Id"}},"title":"PurchaseIntentCreate","type":"object"}
```

### `PurchaseIntentView`

```json
{"additionalProperties":false,"properties":{"amount":{"pattern":"^(0|[1-9][0-9]*)\\.[0-9]{2}$","title":"Amount","type":"string"},"approval_plan_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Approval Plan Hash","type":"string"},"approval_policy_version":{"title":"Approval Policy Version","type":"integer"},"approval_requirement_set_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Approval Requirement Set Id","type":"string"},"approval_status":{"$ref":"#/components/schemas/ApprovalStatus"},"approved_merchant_chain_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Approved Merchant Chain Id","type":"string"},"billing_identity_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Billing Identity Id","type":"string"},"buyer_legal_entity_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Buyer Legal Entity Id","type":"string"},"contract_version_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Contract Version Id","type":"string"},"cost_center_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Cost Center Id","type":"string"},"currency":{"pattern":"^[A-Z]{3}$","title":"Currency","type":"string"},"decision_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Decision Hash","type":"string"},"decision_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Decision Id","type":"string"},"decision_version":{"title":"Decision Version","type":"integer"},"expected_fulfillments":{"items":{"additionalProperties":true,"type":"object"},"title":"Expected Fulfillments","type":"array"},"fee_amount":{"pattern":"^(0|[1-9][0-9]*)\\.[0-9]{2}$","title":"Fee Amount","type":"string"},"fee_schedule_version":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Fee Schedule Version","type":"string"},"fulfillment_completion_policy":{"title":"Fulfillment Completion Policy","type":"string"},"intent_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Intent Hash","type":"string"},"landed_total":{"pattern":"^(0|[1-9][0-9]*)\\.[0-9]{2}$","title":"Landed Total","type":"string"},"line_items":{"items":{"additionalProperties":true,"type":"object"},"title":"Line Items","type":"array"},"locked_at":{"format":"date-time","title":"Locked At","type":"string"},"merchant":{"additionalProperties":{"type":"string"},"title":"Merchant","type":"object"},"merchant_subtotal":{"pattern":"^(0|[1-9][0-9]*)\\.[0-9]{2}$","title":"Merchant Subtotal","type":"string"},"offer_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Offer Id","type":"string"},"offer_version":{"title":"Offer Version","type":"integer"},"organization_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Organization Id","type":"string"},"pack_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Pack Id","type":"string"},"pack_version":{"title":"Pack Version","type":"integer"},"procurement_gate_result_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Procurement Gate Result Hash","type":"string"},"procurement_plan_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Procurement Plan Id","type":"string"},"purchase_intent_group_id":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Purchase Intent Group Id"},"purchase_intent_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Purchase Intent Id","type":"string"},"purchase_order_ref":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Purchase Order Ref"},"quote_expires_at":{"format":"date-time","title":"Quote Expires At","type":"string"},"quote_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Quote Id","type":"string"},"quote_version":{"title":"Quote Version","type":"integer"},"schema_version":{"title":"Schema Version","type":"string"},"selection_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Selection Id","type":"string"},"seller_contracting_entity_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Seller Contracting Entity Id","type":"string"},"solution_plan_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Solution Plan Id","type":"string"},"stack_patch_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Stack Patch Id","type":"string"},"tax_amount":{"pattern":"^(0|[1-9][0-9]*)\\.[0-9]{2}$","title":"Tax Amount","type":"string"}},"required":["schema_version","purchase_intent_id","organization_id","decision_id","decision_version","decision_hash","selection_id","solution_plan_id","stack_patch_id","procurement_plan_id","procurement_gate_result_hash","pack_id","pack_version","offer_id","offer_version","quote_id","quote_version","quote_expires_at","merchant","approved_merchant_chain_id","amount","currency","line_items","expected_fulfillments","fulfillment_completion_policy","buyer_legal_entity_id","seller_contracting_entity_id","billing_identity_id","cost_center_id","merchant_subtotal","tax_amount","fee_amount","fee_schedule_version","contract_version_id","landed_total","approval_policy_version","approval_requirement_set_id","approval_plan_hash","approval_status","intent_hash","locked_at"],"title":"PurchaseIntentView","type":"object"}
```

### `PurchaseStatusView`

```json
{"additionalProperties":false,"properties":{"approval_status":{"$ref":"#/components/schemas/ApprovalStatus"},"handoff_status":{"anyOf":[{"enum":["READY","OPENED","EXPIRED","CANCELLED"],"type":"string"},{"type":"null"}],"title":"Handoff Status"},"outcome_state":{"enum":["NOT_MEASURED","MEASURING","ACHIEVED","NOT_ACHIEVED","INCONCLUSIVE"],"title":"Outcome State","type":"string"},"purchase_intent_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Purchase Intent Id","type":"string"},"purchase_state":{"enum":["AWAITING_APPROVAL","READY_FOR_HANDOFF","HANDOFF_OPENED","HANDOFF_EXPIRED","HANDOFF_CANCELLED"],"title":"Purchase State","type":"string"}},"required":["purchase_intent_id","approval_status","handoff_status","purchase_state","outcome_state"],"title":"PurchaseStatusView","type":"object"}
```

### `QualificationApprovalCreate`

```json
{"additionalProperties":false,"properties":{"action":{"enum":["APPROVE","REJECT"],"title":"Action","type":"string"},"reason":{"maxLength":1000,"minLength":3,"title":"Reason","type":"string"}},"required":["action","reason"],"title":"QualificationApprovalCreate","type":"object"}
```

### `QualificationConsentCreate`

```json
{"additionalProperties":false,"properties":{"shared_fields":{"additionalProperties":true,"title":"Shared Fields","type":"object"}},"required":["shared_fields"],"title":"QualificationConsentCreate","type":"object"}
```

### `QualificationEngagementView`

```json
{"additionalProperties":false,"properties":{"consents":{"items":{"additionalProperties":true,"type":"object"},"title":"Consents","type":"array"},"engagement":{"additionalProperties":true,"title":"Engagement","type":"object"},"introduction":{"anyOf":[{"additionalProperties":true,"type":"object"},{"type":"null"}],"title":"Introduction"},"seller_response":{"anyOf":[{"additionalProperties":true,"type":"object"},{"type":"null"}],"title":"Seller Response"}},"required":["engagement","seller_response","consents","introduction"],"title":"QualificationEngagementView","type":"object"}
```

### `QualificationEventFeed`

```json
{"additionalProperties":false,"properties":{"events":{"items":{"additionalProperties":true,"type":"object"},"title":"Events","type":"array"},"next_cursor":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Next Cursor"}},"required":["events","next_cursor"],"title":"QualificationEventFeed","type":"object"}
```

### `QualificationInboxView`

```json
{"additionalProperties":false,"properties":{"items":{"items":{"additionalProperties":true,"type":"object"},"title":"Items","type":"array"},"next_cursor":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Next Cursor"},"workspace":{"enum":["BUYER","SELLER"],"title":"Workspace","type":"string"}},"required":["workspace","items"],"title":"QualificationInboxView","type":"object"}
```

### `QualificationIntegrityView`

```json
{"additionalProperties":false,"properties":{"checked_at":{"title":"Checked At","type":"string"},"checks":{"items":{"additionalProperties":true,"type":"object"},"title":"Checks","type":"array"},"mission_id":{"title":"Mission Id","type":"string"},"verdict":{"enum":["PASS","FAIL","PENDING"],"title":"Verdict","type":"string"}},"required":["mission_id","verdict","checks","checked_at"],"title":"QualificationIntegrityView","type":"object"}
```

### `QualificationIntroductionCreate`

```json
{"additionalProperties":false,"properties":{"shared_fields":{"additionalProperties":true,"title":"Shared Fields","type":"object"}},"required":["shared_fields"],"title":"QualificationIntroductionCreate","type":"object"}
```

### `QualificationMissionCreate`

```json
{"additionalProperties":false,"properties":{"buyer_context":{"additionalProperties":true,"title":"Buyer Context","type":"object"},"company_context_item_ids":{"items":{"type":"string"},"maxItems":100,"title":"Company Context Item Ids","type":"array"},"procurement_policy":{"additionalProperties":true,"title":"Procurement Policy","type":"object"},"requirement_brief":{"$ref":"#/components/schemas/RequirementBriefCreate"}},"required":["buyer_context","requirement_brief","procurement_policy"],"title":"QualificationMissionCreate","type":"object"}
```

### `QualificationMissionView`

```json
{"additionalProperties":false,"properties":{"attempts":{"items":{"additionalProperties":true,"type":"object"},"title":"Attempts","type":"array"},"decision":{"anyOf":[{"additionalProperties":true,"type":"object"},{"type":"null"}],"title":"Decision"},"engagement":{"anyOf":[{"additionalProperties":true,"type":"object"},{"type":"null"}],"title":"Engagement"},"integrity":{"additionalProperties":true,"title":"Integrity","type":"object"},"mission":{"additionalProperties":true,"title":"Mission","type":"object"}},"required":["mission","attempts","decision","engagement","integrity"],"title":"QualificationMissionView","type":"object"}
```

### `QualificationMutationView`

```json
{"additionalProperties":false,"properties":{"input_digest":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Input Digest"},"replayed":{"default":false,"title":"Replayed","type":"boolean"},"resource_id":{"title":"Resource Id","type":"string"},"resource_type":{"title":"Resource Type","type":"string"},"state":{"title":"State","type":"string"}},"required":["resource_type","resource_id","state"],"title":"QualificationMutationView","type":"object"}
```

### `QualificationSellerResponseCreate`

```json
{"additionalProperties":false,"properties":{"cited_evidence_ids":{"items":{"type":"string"},"maxItems":30,"title":"Cited Evidence Ids","type":"array"},"message":{"anyOf":[{"maxLength":2000,"type":"string"},{"type":"null"}],"title":"Message"},"response":{"enum":["FIT","ANTI_FIT","NEEDS_INFO"],"title":"Response","type":"string"}},"required":["response"],"title":"QualificationSellerResponseCreate","type":"object"}
```

### `QuietHours`

```json
{"additionalProperties":false,"properties":{"enabled":{"default":false,"title":"Enabled","type":"boolean"},"end":{"default":"07:00","pattern":"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$","title":"End","type":"string"},"start":{"default":"22:00","pattern":"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$","title":"Start","type":"string"},"timezone":{"default":"Asia/Kolkata","maxLength":80,"minLength":3,"title":"Timezone","type":"string"}},"title":"QuietHours","type":"object"}
```

### `RankStability`

```json
{"enum":["STABLE","UNSTABLE","UNDETERMINED"],"title":"RankStability","type":"string"}
```

### `RankStabilityProjection`

```json
{"additionalProperties":false,"properties":{"evidence_frontier":{"items":{"$ref":"#/components/schemas/EvidenceFrontierItem"},"title":"Evidence Frontier","type":"array"},"status":{"$ref":"#/components/schemas/RankStability"},"summary":{"maxLength":500,"minLength":1,"title":"Summary","type":"string"}},"required":["status","summary","evidence_frontier"],"title":"RankStabilityProjection","type":"object"}
```

### `RequestVisibility`

```json
{"enum":["PRIVATE","SELECTIVE","OPEN_RFP"],"title":"RequestVisibility","type":"string"}
```

### `RequirementBriefCreate`

```json
{"additionalProperties":false,"properties":{"category":{"maxLength":80,"minLength":2,"title":"Category","type":"string"},"criteria":{"items":{"$ref":"#/components/schemas/RequirementCriterion"},"maxItems":30,"minItems":1,"title":"Criteria","type":"array"},"goal":{"maxLength":2000,"minLength":10,"title":"Goal","type":"string"},"seller_visible_requirements":{"additionalProperties":true,"title":"Seller Visible Requirements","type":"object"}},"required":["category","goal","criteria"],"title":"RequirementBriefCreate","type":"object"}
```

### `RequirementBriefView`

```json
{"additionalProperties":false,"properties":{"allowed_stack_context":{"additionalProperties":true,"title":"Allowed Stack Context","type":"object"},"category_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Category Id","type":"string"},"content_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Content Hash","type":"string"},"data_profile":{"additionalProperties":true,"title":"Data Profile","type":"object"},"desired_outcome":{"title":"Desired Outcome","type":"string"},"expires_at":{"format":"date-time","title":"Expires At","type":"string"},"hard_requirements":{"items":{"additionalProperties":true,"type":"object"},"title":"Hard Requirements","type":"array"},"intent":{"title":"Intent","type":"string"},"preferences":{"items":{"additionalProperties":true,"type":"object"},"title":"Preferences","type":"array"},"purchase_brief_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Purchase Brief Id","type":"string"},"purchase_brief_version":{"title":"Purchase Brief Version","type":"integer"},"requirement_brief_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Requirement Brief Id","type":"string"},"schema_version":{"title":"Schema Version","type":"string"},"seller_questions":{"items":{"type":"string"},"title":"Seller Questions","type":"array"},"team":{"additionalProperties":true,"title":"Team","type":"object"},"version":{"title":"Version","type":"integer"},"visibility":{"$ref":"#/components/schemas/RequestVisibility"}},"required":["schema_version","requirement_brief_id","purchase_brief_id","purchase_brief_version","version","visibility","category_id","intent","desired_outcome","team","data_profile","hard_requirements","preferences","allowed_stack_context","seller_questions","expires_at","content_hash"],"title":"RequirementBriefView","type":"object"}
```

### `RequirementCriterion`

```json
{"additionalProperties":false,"properties":{"id":{"maxLength":64,"minLength":1,"pattern":"^[A-Za-z0-9_-]+$","title":"Id","type":"string"},"label":{"maxLength":200,"minLength":1,"title":"Label","type":"string"},"priority":{"default":"MUST","enum":["MUST","SHOULD","COULD"],"title":"Priority","type":"string"},"requirement":{"maxLength":1000,"minLength":1,"title":"Requirement","type":"string"}},"required":["id","label","requirement"],"title":"RequirementCriterion","type":"object"}
```

### `ResultArtifact`

```json
{"additionalProperties":false,"properties":{"actor_ref":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Actor Ref"},"href":{"maxLength":500,"pattern":"^/","title":"Href","type":"string"},"id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Id","type":"string"},"occurred_at":{"format":"date-time","title":"Occurred At","type":"string"},"owner_role":{"$ref":"#/components/schemas/ActorRole"},"safe_label":{"maxLength":200,"minLength":1,"title":"Safe Label","type":"string"},"stack_patch_id":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Stack Patch Id"},"type":{"$ref":"#/components/schemas/ResultArtifactType"},"verification_state":{"enum":["PENDING","VERIFIED","FAILED","REVOKED"],"title":"Verification State","type":"string"},"verified_at":{"anyOf":[{"format":"date-time","type":"string"},{"type":"null"}],"title":"Verified At"}},"required":["id","type","verification_state","actor_ref","owner_role","occurred_at","safe_label","href","stack_patch_id"],"title":"ResultArtifact","type":"object"}
```

### `ResultArtifactType`

```json
{"enum":["DECISION_RECORD","CONFIGURATION_CHANGE","CONTRACT_CONFIRMATION","CANCELLATION_CONFIRMATION","MIGRATION_RECORD","STACK_PATCH","OUTCOME_CHECKPOINT"],"title":"ResultArtifactType","type":"string"}
```

### `ScoreComponentView`

```json
{"additionalProperties":false,"properties":{"conservative_contribution":{"$ref":"#/components/schemas/ExactRatioView"},"conservative_satisfaction":{"$ref":"#/components/schemas/ExactRatioView"},"coverage_weight":{"maximum":5.0,"minimum":1.0,"title":"Coverage Weight","type":"integer"},"criterion_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Criterion Id","type":"string"},"evidence_ids":{"items":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},"title":"Evidence Ids","type":"array"},"evidence_state":{"enum":["ACCEPTABLE","UNKNOWN","STALE","CONFLICT"],"title":"Evidence State","type":"string"},"optimistic_contribution":{"$ref":"#/components/schemas/ExactRatioView"},"optimistic_satisfaction":{"$ref":"#/components/schemas/ExactRatioView"},"prior_label":{"anyOf":[{"maxLength":200,"type":"string"},{"type":"null"}],"title":"Prior Label"},"weight":{"maximum":5.0,"minimum":1.0,"title":"Weight","type":"integer"}},"required":["criterion_id","weight","coverage_weight","conservative_satisfaction","optimistic_satisfaction","conservative_contribution","optimistic_contribution","evidence_ids","evidence_state","prior_label"],"title":"ScoreComponentView","type":"object"}
```

### `SelectedActionPlan`

```json
{"additionalProperties":false,"properties":{"action_type":{"enum":["REUSE_EXISTING","CONFIGURE_EXISTING","NO_ACTION","BUY","RENEW","RESIZE","REPLACE","CANCEL"],"title":"Action Type","type":"string"},"decision_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Decision Hash","type":"string"},"decision_version":{"minimum":1.0,"title":"Decision Version","type":"integer"},"execution_steps":{"items":{"$ref":"#/components/schemas/ExecutionStep"},"title":"Execution Steps","type":"array"},"href":{"maxLength":500,"minLength":1,"title":"Href","type":"string"},"id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Id","type":"string"},"selected_at":{"format":"date-time","title":"Selected At","type":"string"},"selected_by_role":{"$ref":"#/components/schemas/ActorRole"},"selection_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Selection Id","type":"string"},"state":{"$ref":"#/components/schemas/PlanSelectionState"}},"required":["id","action_type","state","selected_at","selected_by_role","selection_id","decision_version","decision_hash","execution_steps","href"],"title":"SelectedActionPlan","type":"object"}
```

### `SellerActionDescriptor`

```json
{"additionalProperties":false,"properties":{"href":{"maxLength":500,"pattern":"^/","title":"Href","type":"string"},"id":{"pattern":"^[A-Z][A-Z0-9_]{2,63}$","title":"Id","type":"string"},"label":{"maxLength":100,"minLength":1,"title":"Label","type":"string"},"method":{"enum":["GET","POST","PATCH"],"title":"Method","type":"string"},"requires_confirmation":{"title":"Requires Confirmation","type":"boolean"}},"required":["id","label","method","href","requires_confirmation"],"title":"SellerActionDescriptor","type":"object"}
```

### `SellerActivityMetrics`

```json
{"additionalProperties":false,"properties":{"answer_rendered_count":{"minimum":0.0,"title":"Answer Rendered Count","type":"integer"},"href":{"maxLength":500,"pattern":"^/","title":"Href","type":"string"},"measurement_label":{"const":"OBSERVATIONAL_NOT_CAUSAL","default":"OBSERVATIONAL_NOT_CAUSAL","title":"Measurement Label","type":"string"},"observed_self_service_count":{"minimum":0.0,"title":"Observed Self Service Count","type":"integer"},"seller_handoff_requested_count":{"minimum":0.0,"title":"Seller Handoff Requested Count","type":"integer"},"window_end":{"format":"date-time","title":"Window End","type":"string"},"window_start":{"format":"date-time","title":"Window Start","type":"string"}},"required":["window_start","window_end","answer_rendered_count","seller_handoff_requested_count","observed_self_service_count","href"],"title":"SellerActivityMetrics","type":"object"}
```

### `SellerActor`

```json
{"additionalProperties":false,"properties":{"capabilities":{"items":{"$ref":"#/components/schemas/SellerCapability"},"title":"Capabilities","type":"array"},"role":{"enum":["SELLER_EDITOR","SELLER_REVIEWER","PLATFORM_OPERATOR"],"title":"Role","type":"string"}},"required":["role","capabilities"],"title":"SellerActor","type":"object"}
```

### `SellerCapability`

```json
{"enum":["CLAIM_PRODUCT","VIEW_OWN_DRAFT","EDIT_CLAIMS","ADD_EVIDENCE","SUBMIT_REVIEW","REQUEST_CHANGES","APPROVE_REVIEW","REJECT_REVIEW","PUBLISH","SUSPEND","EXPORT","VIEW_ACTIVITY_METRICS","RETRY_PUBLICATION"],"title":"SellerCapability","type":"string"}
```

### `SellerClaimCreate`

```json
{"additionalProperties":false,"properties":{"authority_proof_reference":{"maxLength":500,"minLength":3,"title":"Authority Proof Reference","type":"string"},"requested_role":{"$ref":"#/components/schemas/ActorRole","default":"SELLER_EDITOR"}},"required":["authority_proof_reference"],"title":"SellerClaimCreate","type":"object"}
```

### `SellerClaimView`

```json
{"additionalProperties":false,"properties":{"claim_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Claim Id","type":"string"},"product_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Product Id","type":"string"},"safe_reason":{"anyOf":[{"maxLength":500,"type":"string"},{"type":"null"}],"title":"Safe Reason"},"state":{"$ref":"#/components/schemas/SellerEvidenceState"},"submitted_at":{"format":"date-time","title":"Submitted At","type":"string"}},"required":["claim_id","product_id","state","submitted_at"],"title":"SellerClaimView","type":"object"}
```

### `SellerEvidenceAttachCreate`

```json
{"additionalProperties":false,"properties":{"claim_fields":{"items":{"type":"string"},"minItems":1,"title":"Claim Fields","type":"array"},"observed_at":{"anyOf":[{"format":"date-time","type":"string"},{"type":"null"}],"title":"Observed At"},"source_class":{"maxLength":80,"minLength":2,"title":"Source Class","type":"string"},"source_reference":{"maxLength":500,"minLength":3,"title":"Source Reference","type":"string"}},"required":["source_reference","source_class","claim_fields"],"title":"SellerEvidenceAttachCreate","type":"object"}
```

### `SellerEvidenceAttachmentView`

```json
{"additionalProperties":false,"properties":{"content_type":{"anyOf":[{"maxLength":120,"minLength":1,"type":"string"},{"type":"null"}],"title":"Content Type"},"draft_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Draft Id","type":"string"},"id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Id","type":"string"},"object_checksum":{"anyOf":[{"pattern":"^sha256:[0-9a-f]{64}$","type":"string"},{"type":"null"}],"title":"Object Checksum"},"size_bytes":{"anyOf":[{"minimum":1.0,"type":"integer"},{"type":"null"}],"title":"Size Bytes"},"source_reference_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Source Reference Hash","type":"string"},"verification_state":{"enum":["UNVERIFIED","PENDING","VERIFIED","REJECTED"],"title":"Verification State","type":"string"},"version_bound":{"default":false,"title":"Version Bound","type":"boolean"}},"required":["id","draft_id","verification_state","source_reference_hash"],"title":"SellerEvidenceAttachmentView","type":"object"}
```

### `SellerEvidenceClaim`

```json
{"additionalProperties":false,"properties":{"evidence_ids":{"items":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},"title":"Evidence Ids","type":"array"},"field":{"maxLength":120,"minLength":1,"title":"Field","type":"string"},"value":{"anyOf":[{"type":"string"},{"type":"integer"},{"type":"boolean"},{"items":{"type":"string"},"type":"array"},{"type":"null"}],"title":"Value"}},"required":["field","value","evidence_ids"],"title":"SellerEvidenceClaim","type":"object"}
```

### `SellerEvidenceProduct`

```json
{"additionalProperties":false,"properties":{"current_version":{"minimum":1.0,"title":"Current Version","type":"integer"},"href":{"maxLength":500,"pattern":"^/","title":"Href","type":"string"},"id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Id","type":"string"},"name":{"maxLength":200,"minLength":1,"title":"Name","type":"string"},"seller_state":{"$ref":"#/components/schemas/SellerEvidenceState"}},"required":["id","name","seller_state","current_version","href"],"title":"SellerEvidenceProduct","type":"object"}
```

### `SellerEvidenceState`

```json
{"enum":["UNCLAIMED","CLAIM_PENDING","CLAIM_DENIED","SELLER_DRAFT","VALIDATION_CONFLICT","IN_REVIEW","CHANGES_REQUESTED","PUBLISH_READY","PUBLISHED","SUPERSEDED","PUBLICATION_FAILED"],"title":"SellerEvidenceState","type":"string"}
```

### `SellerEvidenceView`

```json
{"additionalProperties":false,"properties":{"activity_metrics":{"$ref":"#/components/schemas/SellerActivityMetrics"},"actor":{"$ref":"#/components/schemas/SellerActor"},"available_actions":{"items":{"$ref":"#/components/schemas/SellerActionDescriptor"},"title":"Available Actions","type":"array"},"pack_health":{"$ref":"#/components/schemas/SellerPackHealth"},"product":{"$ref":"#/components/schemas/SellerEvidenceProduct"},"publisher_authority":{"$ref":"#/components/schemas/PublisherAuthorityProjection"},"reusable_answers":{"$ref":"#/components/schemas/SellerReusableAnswers"},"review":{"anyOf":[{"$ref":"#/components/schemas/SellerReviewSummary"},{"type":"null"}]},"validation":{"$ref":"#/components/schemas/SellerValidation"},"version_links":{"$ref":"#/components/schemas/SellerVersionLinks"}},"required":["product","actor","publisher_authority","pack_health","validation","reusable_answers","activity_metrics","available_actions","version_links"],"title":"SellerEvidenceView","type":"object"}
```

### `SellerExportFormat`

```json
{"enum":["JSON","HTML","REUSABLE_ANSWER"],"title":"SellerExportFormat","type":"string"}
```

### `SellerPackDraftPatch`

```json
{"additionalProperties":false,"properties":{"anti_fit_rules":{"items":{"$ref":"#/components/schemas/SellerEvidenceClaim"},"title":"Anti Fit Rules","type":"array"},"base_revision":{"minimum":1.0,"title":"Base Revision","type":"integer"},"claims":{"items":{"$ref":"#/components/schemas/SellerEvidenceClaim"},"title":"Claims","type":"array"},"fit_rules":{"items":{"$ref":"#/components/schemas/SellerEvidenceClaim"},"title":"Fit Rules","type":"array"},"proof_adapter":{"anyOf":[{"$ref":"#/components/schemas/SellerProofAdapterDraft"},{"type":"null"}]}},"required":["base_revision"],"title":"SellerPackDraftPatch","type":"object"}
```

### `SellerPackDraftView`

```json
{"additionalProperties":false,"properties":{"anti_fit_rules":{"items":{"$ref":"#/components/schemas/SellerEvidenceClaim"},"title":"Anti Fit Rules","type":"array"},"claims":{"items":{"$ref":"#/components/schemas/SellerEvidenceClaim"},"title":"Claims","type":"array"},"fit_rules":{"items":{"$ref":"#/components/schemas/SellerEvidenceClaim"},"title":"Fit Rules","type":"array"},"id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Id","type":"string"},"product_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Product Id","type":"string"},"proof_adapter":{"anyOf":[{"$ref":"#/components/schemas/SellerProofAdapterDraft"},{"type":"null"}]},"publisher_authority":{"$ref":"#/components/schemas/PackAuthority"},"revision":{"minimum":1.0,"title":"Revision","type":"integer"},"revision_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Revision Hash","type":"string"},"state":{"$ref":"#/components/schemas/SellerEvidenceState"},"updated_at":{"format":"date-time","title":"Updated At","type":"string"},"validation":{"$ref":"#/components/schemas/SellerValidation"}},"required":["id","product_id","revision","revision_hash","state","publisher_authority","claims","fit_rules","anti_fit_rules","validation","updated_at"],"title":"SellerPackDraftView","type":"object"}
```

### `SellerPackExport`

```json
{"additionalProperties":false,"properties":{"content_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Content Hash","type":"string"},"format":{"$ref":"#/components/schemas/SellerExportFormat"},"generated_at":{"format":"date-time","title":"Generated At","type":"string"},"href":{"maxLength":500,"pattern":"^/","title":"Href","type":"string"},"pack_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Pack Id","type":"string"},"pack_version":{"minimum":1.0,"title":"Pack Version","type":"integer"},"publisher_authority":{"$ref":"#/components/schemas/PackAuthority"},"verification_summary":{"maxLength":300,"minLength":1,"title":"Verification Summary","type":"string"}},"required":["format","pack_id","pack_version","publisher_authority","verification_summary","generated_at","content_hash","href"],"title":"SellerPackExport","type":"object"}
```

### `SellerPackExportsView`

```json
{"additionalProperties":false,"properties":{"exports":{"items":{"$ref":"#/components/schemas/SellerPackExport"},"title":"Exports","type":"array"}},"required":["exports"],"title":"SellerPackExportsView","type":"object"}
```

### `SellerPackHealth`

```json
{"additionalProperties":false,"properties":{"complete_claim_count":{"minimum":0.0,"title":"Complete Claim Count","type":"integer"},"conflict_count":{"minimum":0.0,"title":"Conflict Count","type":"integer"},"required_claim_count":{"minimum":0.0,"title":"Required Claim Count","type":"integer"},"stale_claim_count":{"minimum":0.0,"title":"Stale Claim Count","type":"integer"},"status":{"enum":["HEALTHY","NEEDS_ATTENTION","BLOCKED"],"title":"Status","type":"string"}},"required":["status","required_claim_count","complete_claim_count","stale_claim_count","conflict_count"],"title":"SellerPackHealth","type":"object"}
```

### `SellerPackVersionView`

```json
{"additionalProperties":false,"properties":{"content_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Content Hash","type":"string"},"id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Id","type":"string"},"product_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Product Id","type":"string"},"proof_adapter":{"anyOf":[{"$ref":"#/components/schemas/SellerProofAdapterDraft"},{"type":"null"}]},"published_at":{"anyOf":[{"format":"date-time","type":"string"},{"type":"null"}],"title":"Published At"},"publisher_authority":{"$ref":"#/components/schemas/PackAuthority"},"state":{"$ref":"#/components/schemas/SellerEvidenceState"},"version":{"minimum":1.0,"title":"Version","type":"integer"}},"required":["id","product_id","version","content_hash","publisher_authority","state"],"title":"SellerPackVersionView","type":"object"}
```

### `SellerProductSearchItem`

```json
{"additionalProperties":false,"properties":{"category":{"maxLength":120,"minLength":1,"title":"Category","type":"string"},"href":{"maxLength":500,"pattern":"^/","title":"Href","type":"string"},"id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Id","type":"string"},"name":{"maxLength":200,"minLength":1,"title":"Name","type":"string"},"public_summary":{"maxLength":1000,"minLength":1,"title":"Public Summary","type":"string"},"publisher_authority":{"$ref":"#/components/schemas/PackAuthority"},"state":{"$ref":"#/components/schemas/SellerEvidenceState"}},"required":["id","name","category","publisher_authority","state","public_summary","href"],"title":"SellerProductSearchItem","type":"object"}
```

### `SellerProductSearchView`

```json
{"additionalProperties":false,"properties":{"results":{"items":{"$ref":"#/components/schemas/SellerProductSearchItem"},"title":"Results","type":"array"}},"required":["results"],"title":"SellerProductSearchView","type":"object"}
```

### `SellerProofAdapterDraft`

```json
{"additionalProperties":false,"properties":{"adapter_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Adapter Id","type":"string"},"artifact_digest":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Artifact Digest","type":"string"},"capabilities":{"items":{"enum":["SUPPORT_SUMMARIZATION","CUSTOMER_EMAIL_OUTPUT","PII_REDACTION"],"type":"string"},"minItems":1,"title":"Capabilities","type":"array"},"conformance_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Conformance Hash","type":"string"},"declared_region":{"enum":["EU","IN","US"],"title":"Declared Region","type":"string"},"fixed_price":{"$ref":"#/components/schemas/SellerProofAdapterPrice"},"protocol_version":{"const":"TrialCase/v0","title":"Protocol Version","type":"string"}},"required":["adapter_id","artifact_digest","protocol_version","capabilities","declared_region","fixed_price","conformance_hash"],"title":"SellerProofAdapterDraft","type":"object"}
```

### `SellerProofAdapterPrice`

```json
{"additionalProperties":false,"properties":{"amount":{"pattern":"^(0|[1-9][0-9]*)\\.[0-9]{2}$","title":"Amount","type":"string"},"currency":{"const":"USD","default":"USD","title":"Currency","type":"string"}},"required":["amount"],"title":"SellerProofAdapterPrice","type":"object"}
```

### `SellerPublishCreate`

```json
{"additionalProperties":false,"properties":{"revision_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Revision Hash","type":"string"}},"required":["revision_hash"],"title":"SellerPublishCreate","type":"object"}
```

### `SellerReusableAnswers`

```json
{"additionalProperties":false,"properties":{"formats":{"items":{"$ref":"#/components/schemas/SellerExportFormat"},"title":"Formats","type":"array"},"href":{"anyOf":[{"maxLength":500,"pattern":"^/","type":"string"},{"type":"null"}],"title":"Href"},"published_answer_count":{"minimum":0.0,"title":"Published Answer Count","type":"integer"},"published_version":{"anyOf":[{"minimum":1.0,"type":"integer"},{"type":"null"}],"title":"Published Version"}},"required":["published_answer_count","formats"],"title":"SellerReusableAnswers","type":"object"}
```

### `SellerReviewDecision`

```json
{"enum":["REQUEST_CHANGES","APPROVE","REJECT"],"title":"SellerReviewDecision","type":"string"}
```

### `SellerReviewDecisionCreate`

```json
{"additionalProperties":false,"properties":{"decision":{"$ref":"#/components/schemas/SellerReviewDecision"},"reason":{"maxLength":1000,"minLength":3,"title":"Reason","type":"string"},"revision_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Revision Hash","type":"string"}},"required":["decision","revision_hash","reason"],"title":"SellerReviewDecisionCreate","type":"object"}
```

### `SellerReviewDecisionView`

```json
{"additionalProperties":false,"properties":{"actor_role":{"$ref":"#/components/schemas/ActorRole"},"decision":{"$ref":"#/components/schemas/SellerReviewDecision"},"draft_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Draft Id","type":"string"},"id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Id","type":"string"},"occurred_at":{"format":"date-time","title":"Occurred At","type":"string"},"reason":{"title":"Reason","type":"string"},"revision_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Revision Hash","type":"string"}},"required":["id","draft_id","decision","revision_hash","actor_role","reason","occurred_at"],"title":"SellerReviewDecisionView","type":"object"}
```

### `SellerReviewSummary`

```json
{"additionalProperties":false,"properties":{"decision":{"anyOf":[{"$ref":"#/components/schemas/SellerReviewDecision"},{"type":"null"}]},"reason":{"anyOf":[{"maxLength":500,"type":"string"},{"type":"null"}],"title":"Reason"},"recorded_at":{"anyOf":[{"format":"date-time","type":"string"},{"type":"null"}],"title":"Recorded At"},"review_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Review Id","type":"string"},"reviewer_role":{"enum":["SELLER_REVIEWER","PLATFORM_OPERATOR"],"title":"Reviewer Role","type":"string"},"revision_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Revision Hash","type":"string"},"status":{"enum":["PENDING","COMPLETED"],"title":"Status","type":"string"}},"required":["review_id","revision_hash","status","decision","reviewer_role","recorded_at"],"title":"SellerReviewSummary","type":"object"}
```

### `SellerSubmitReviewCreate`

```json
{"additionalProperties":false,"properties":{"revision_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Revision Hash","type":"string"}},"required":["revision_hash"],"title":"SellerSubmitReviewCreate","type":"object"}
```

### `SellerSuspendCreate`

```json
{"additionalProperties":false,"properties":{"effective_at":{"format":"date-time","title":"Effective At","type":"string"},"reason":{"maxLength":1000,"minLength":3,"title":"Reason","type":"string"}},"required":["reason","effective_at"],"title":"SellerSuspendCreate","type":"object"}
```

### `SellerValidation`

```json
{"additionalProperties":false,"properties":{"gaps":{"items":{"$ref":"#/components/schemas/SellerValidationGap"},"title":"Gaps","type":"array"},"status":{"enum":["NOT_RUN","VALID","HAS_GAPS","CONFLICT"],"title":"Status","type":"string"}},"required":["status","gaps"],"title":"SellerValidation","type":"object"}
```

### `SellerValidationGap`

```json
{"additionalProperties":false,"properties":{"field":{"pattern":"^[a-z][a-z0-9_.]{2,127}$","title":"Field","type":"string"},"href":{"maxLength":500,"pattern":"^/","title":"Href","type":"string"},"id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Id","type":"string"},"safe_message":{"maxLength":300,"minLength":1,"title":"Safe Message","type":"string"}},"required":["id","field","safe_message","href"],"title":"SellerValidationGap","type":"object"}
```

### `SellerVersionLinks`

```json
{"additionalProperties":false,"properties":{"current":{"maxLength":500,"pattern":"^/","title":"Current","type":"string"},"previous":{"anyOf":[{"maxLength":500,"pattern":"^/","type":"string"},{"type":"null"}],"title":"Previous"}},"required":["current"],"title":"SellerVersionLinks","type":"object"}
```

### `SolutionActionType`

```json
{"enum":["REUSE_EXISTING","CONFIGURE_EXISTING","NO_ACTION","BUY","RENEW","RESIZE","REPLACE","CONSOLIDATE","CANCEL"],"title":"SolutionActionType","type":"string"}
```

### `SolutionOption`

```json
{"additionalProperties":false,"properties":{"action_type":{"$ref":"#/components/schemas/SolutionActionType"},"components":{"items":{"$ref":"#/components/schemas/ProductEvidenceComponent"},"title":"Components","type":"array"},"default_comparison":{"$ref":"#/components/schemas/DefaultComparison"},"evidence":{"items":{"$ref":"#/components/schemas/EvidenceSummary"},"title":"Evidence","type":"array"},"evidence_coverage":{"$ref":"#/components/schemas/EvidenceCoverageView"},"evidence_frontier":{"items":{"$ref":"#/components/schemas/EvidenceFrontierItem"},"title":"Evidence Frontier","type":"array"},"id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Id","type":"string"},"label":{"maxLength":200,"minLength":1,"title":"Label","type":"string"},"maximum_evidence_age_ratio":{"$ref":"#/components/schemas/EvidenceAgeBounds"},"merchant":{"anyOf":[{"$ref":"#/components/schemas/MerchantProjection"},{"type":"null"}]},"ordering_frontier_member":{"title":"Ordering Frontier Member","type":"boolean"},"permitted_resolution":{"anyOf":[{"maxLength":300,"type":"string"},{"type":"null"}],"title":"Permitted Resolution"},"preference_score":{"$ref":"#/components/schemas/PreferenceScoreBounds"},"quote_policy_reason":{"maxLength":120,"minLength":1,"title":"Quote Policy Reason","type":"string"},"quote_required":{"title":"Quote Required","type":"boolean"},"reason":{"maxLength":500,"minLength":1,"title":"Reason","type":"string"},"reason_code":{"anyOf":[{"maxLength":80,"type":"string"},{"type":"null"}],"title":"Reason Code"},"resolution_frontier_member":{"title":"Resolution Frontier Member","type":"boolean"},"seller_positioning":{"anyOf":[{"maxLength":500,"type":"string"},{"type":"null"}],"title":"Seller Positioning"},"stack_risk":{"$ref":"#/components/schemas/StackRiskBounds"},"status":{"$ref":"#/components/schemas/SolutionOptionStatus"},"total_cost":{"$ref":"#/components/schemas/TotalCostBounds"}},"required":["id","action_type","label","status","reason","default_comparison","preference_score","ordering_frontier_member","resolution_frontier_member","quote_required","quote_policy_reason","stack_risk","total_cost","evidence_coverage","maximum_evidence_age_ratio","evidence_frontier","components","evidence"],"title":"SolutionOption","type":"object"}
```

### `SolutionOptionStatus`

```json
{"enum":["SUPPORTED","SUPPORTED_WITH_EXCEPTION","NEEDS_CONDITION","BLOCKED_BY_COMPANY_REQUIREMENT","VENDOR_NOT_SUPPORTED","UNAVAILABLE","NEEDS_EVIDENCE","EVIDENCE_CONFLICT","AUTHORITY_REQUIRED","RESEARCH_ONLY"],"title":"SolutionOptionStatus","type":"string"}
```

### `SolutionPlanLifecycle`

```json
{"enum":["CANDIDATE","RESOLUTION_PENDING","EXECUTABLE","BLOCKED"],"title":"SolutionPlanLifecycle","type":"string"}
```

### `SolutionPlanRecord`

```json
{"additionalProperties":false,"properties":{"action_type":{"$ref":"#/components/schemas/SolutionActionType"},"autonomous_execution_allowed":{"title":"Autonomous Execution Allowed","type":"boolean"},"component_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Component Hash","type":"string"},"components":{"items":{"$ref":"#/components/schemas/PlanComponentView"},"title":"Components","type":"array"},"construction_lifecycle":{"const":"CANDIDATE","title":"Construction Lifecycle","type":"string"},"dimensions":{"$ref":"#/components/schemas/PlanDimensionsView"},"gate_results":{"items":{"$ref":"#/components/schemas/GateResultView"},"title":"Gate Results","type":"array"},"lifecycle":{"$ref":"#/components/schemas/SolutionPlanLifecycle"},"ordering_frontier_member":{"title":"Ordering Frontier Member","type":"boolean"},"permitted_resolution":{"anyOf":[{"maxLength":300,"type":"string"},{"type":"null"}],"title":"Permitted Resolution"},"primary_reason":{"anyOf":[{"$ref":"#/components/schemas/GateReasonView"},{"type":"null"}]},"quote_policy_reason":{"maxLength":100,"minLength":1,"title":"Quote Policy Reason","type":"string"},"quote_required":{"title":"Quote Required","type":"boolean"},"rank":{"anyOf":[{"minimum":1.0,"type":"integer"},{"type":"null"}],"title":"Rank"},"resolution_frontier_member":{"title":"Resolution Frontier Member","type":"boolean"},"score_components":{"items":{"$ref":"#/components/schemas/ScoreComponentView"},"title":"Score Components","type":"array"},"solution_plan_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Solution Plan Id","type":"string"},"stable_action_ids":{"items":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},"minItems":1,"title":"Stable Action Ids","type":"array"},"stack_patch_id":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Stack Patch Id"},"status":{"$ref":"#/components/schemas/ComponentStatus"}},"required":["solution_plan_id","action_type","components","component_hash","construction_lifecycle","lifecycle","status","primary_reason","gate_results","score_components","dimensions","stable_action_ids","rank","ordering_frontier_member","resolution_frontier_member","quote_required","quote_policy_reason","permitted_resolution","autonomous_execution_allowed","stack_patch_id"],"title":"SolutionPlanRecord","type":"object"}
```

### `StackChangeProjection`

```json
{"additionalProperties":false,"properties":{"added":{"items":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},"title":"Added","type":"array"},"dependency_changed":{"items":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},"title":"Dependency Changed","type":"array"},"href":{"maxLength":500,"minLength":1,"title":"Href","type":"string"},"id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Id","type":"string"},"removed":{"items":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},"title":"Removed","type":"array"},"retained":{"items":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},"title":"Retained","type":"array"},"staged_for_removal":{"items":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},"title":"Staged For Removal","type":"array"},"status":{"enum":["PROPOSED","STAGED","APPLIED","REJECTED","SUPERSEDED"],"title":"Status","type":"string"},"summary":{"maxLength":500,"minLength":1,"title":"Summary","type":"string"}},"required":["id","status","summary","added","removed","staged_for_removal","retained","dependency_changed","href"],"title":"StackChangeProjection","type":"object"}
```

### `StackPatchView`

```json
{"additionalProperties":false,"properties":{"base_snapshot":{"minimum":1.0,"title":"Base Snapshot","type":"integer"},"content_hash":{"pattern":"^sha256:[0-9a-f]{64}$","title":"Content Hash","type":"string"},"cost_impact":{"additionalProperties":true,"title":"Cost Impact","type":"object"},"created_at":{"format":"date-time","title":"Created At","type":"string"},"decision_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Decision Id","type":"string"},"expected_outcome":{"title":"Expected Outcome","type":"string"},"operations":{"items":{"additionalProperties":true,"type":"object"},"title":"Operations","type":"array"},"organization_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Organization Id","type":"string"},"patch_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Patch Id","type":"string"},"prerequisites":{"items":{"type":"string"},"title":"Prerequisites","type":"array"},"risk":{"enum":["LOW","MEDIUM","HIGH","CRITICAL"],"title":"Risk","type":"string"},"rollback_plan":{"items":{"type":"string"},"title":"Rollback Plan","type":"array"},"schema_version":{"title":"Schema Version","type":"string"},"solution_plan_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Solution Plan Id","type":"string"},"status":{"enum":["PROPOSED","STAGED","APPROVED","APPLYING","APPLIED","REJECTED","CONFLICT","FAILED"],"title":"Status","type":"string"}},"required":["schema_version","patch_id","organization_id","base_snapshot","decision_id","solution_plan_id","status","operations","prerequisites","rollback_plan","cost_impact","risk","expected_outcome","created_at","content_hash"],"title":"StackPatchView","type":"object"}
```

### `StackRisk`

```json
{"enum":["LOW","MEDIUM","HIGH","CRITICAL"],"title":"StackRisk","type":"string"}
```

### `StackRiskBounds`

```json
{"additionalProperties":false,"properties":{"base":{"anyOf":[{"$ref":"#/components/schemas/StackRisk"},{"$ref":"#/components/schemas/BoundUnavailableView"}],"title":"Base"},"lower":{"anyOf":[{"$ref":"#/components/schemas/StackRisk"},{"$ref":"#/components/schemas/BoundUnavailableView"}],"title":"Lower"},"upper":{"anyOf":[{"$ref":"#/components/schemas/StackRisk"},{"$ref":"#/components/schemas/BoundUnavailableView"}],"title":"Upper"}},"required":["base","lower","upper"],"title":"StackRiskBounds","type":"object"}
```

### `StackfileView`

```json
{"additionalProperties":false,"properties":{"current":{"additionalProperties":true,"title":"Current","type":"object"},"organization_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Organization Id","type":"string"},"proposed_patch":{"anyOf":[{"$ref":"#/components/schemas/StackPatchView"},{"type":"null"}]}},"required":["organization_id","current"],"title":"StackfileView","type":"object"}
```

### `StageHistoryEntry`

```json
{"additionalProperties":false,"properties":{"checkpoint_id":{"anyOf":[{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","type":"string"},{"type":"null"}],"title":"Checkpoint Id"},"completed_at":{"anyOf":[{"format":"date-time","type":"string"},{"type":"null"}],"title":"Completed At"},"href":{"maxLength":500,"minLength":1,"title":"Href","type":"string"},"stage":{"$ref":"#/components/schemas/DecisionStage"},"status":{"$ref":"#/components/schemas/StageStatus"}},"required":["stage","status","checkpoint_id","href"],"title":"StageHistoryEntry","type":"object"}
```

### `StageStatus`

```json
{"enum":["NOT_STARTED","READY","CURRENT","WAITING","BLOCKED","COMPLETED","SUPERSEDED"],"title":"StageStatus","type":"string"}
```

### `TotalCostBounds`

```json
{"additionalProperties":false,"properties":{"base":{"anyOf":[{"$ref":"#/components/schemas/MoneyViewV2"},{"$ref":"#/components/schemas/BoundUnavailableView"}],"title":"Base"},"high":{"anyOf":[{"$ref":"#/components/schemas/MoneyViewV2"},{"$ref":"#/components/schemas/BoundUnavailableView"}],"title":"High"},"low":{"anyOf":[{"$ref":"#/components/schemas/MoneyViewV2"},{"$ref":"#/components/schemas/BoundUnavailableView"}],"title":"Low"}},"required":["low","base","high"],"title":"TotalCostBounds","type":"object"}
```

### `TruthValue`

```json
{"enum":["TRUE","FALSE","UNKNOWN","CONFLICT","UNRESOLVED"],"title":"TruthValue","type":"string"}
```

### `UIActionCapability`

```json
{"enum":["VIEW_DECISION","EDIT_REQUEST","ANSWER_TASK","VIEW_PRIVATE_COMPANY_FACTS","KEEP_OPTION","ELIMINATE_OPTION","ASK_VENDOR","SAVE_OPTION","REQUEST_EVIDENCE","SELECT_PLAN","ACCEPT_EXCEPTION","APPROVE_POLICY","APPROVE_BUDGET","OPEN_PAYMENT_HANDOFF","EXECUTE_CONFIGURATION","PROVIDE_OUTCOME","EXPORT_AUDIT","EDIT_PRODUCT_EVIDENCE","REVIEW_PRODUCT_EVIDENCE","PUBLISH_PRODUCT_EVIDENCE","SUSPEND_PRODUCT_EVIDENCE"],"title":"UIActionCapability","type":"string"}
```

### `VersionLinks`

```json
{"additionalProperties":false,"properties":{"current":{"maxLength":500,"pattern":"^/","title":"Current","type":"string"},"previous":{"anyOf":[{"maxLength":500,"pattern":"^/","type":"string"},{"type":"null"}],"title":"Previous"},"superseded_by":{"anyOf":[{"maxLength":500,"pattern":"^/","type":"string"},{"type":"null"}],"title":"Superseded By"}},"required":["current"],"title":"VersionLinks","type":"object"}
```

### `WorkflowAccepted`

```json
{"additionalProperties":false,"properties":{"events_url":{"title":"Events Url","type":"string"},"status_url":{"title":"Status Url","type":"string"},"workflow_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Workflow Id","type":"string"}},"required":["workflow_id","status_url","events_url"],"title":"WorkflowAccepted","type":"object"}
```

### `WorkflowActor`

```json
{"additionalProperties":false,"properties":{"capabilities":{"items":{"$ref":"#/components/schemas/UIActionCapability"},"title":"Capabilities","type":"array"},"role":{"$ref":"#/components/schemas/ActorRole"}},"required":["role","capabilities"],"title":"WorkflowActor","type":"object"}
```

### `WorkflowProjection`

```json
{"additionalProperties":false,"properties":{"active_operation":{"anyOf":[{"$ref":"#/components/schemas/ActiveOperation"},{"type":"null"}]},"actor":{"$ref":"#/components/schemas/WorkflowActor"},"available_actions":{"items":{"$ref":"#/components/schemas/ActionDescriptor"},"title":"Available Actions","type":"array"},"blocking_tasks":{"items":{"$ref":"#/components/schemas/BlockingTask"},"title":"Blocking Tasks","type":"array"},"current_stage":{"$ref":"#/components/schemas/DecisionStage"},"stage_history":{"items":{"$ref":"#/components/schemas/StageHistoryEntry"},"title":"Stage History","type":"array"},"version_links":{"$ref":"#/components/schemas/VersionLinks"}},"required":["current_stage","actor","available_actions","blocking_tasks","stage_history","version_links"],"title":"WorkflowProjection","type":"object"}
```

### `WorkflowView`

```json
{"additionalProperties":false,"properties":{"aggregate_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Aggregate Id","type":"string"},"operation":{"title":"Operation","type":"string"},"result_reference":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Result Reference"},"safe_error_code":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Safe Error Code"},"status":{"enum":["PENDING","RUNNING","COMPLETED","FAILED"],"title":"Status","type":"string"},"workflow_id":{"maxLength":128,"minLength":3,"pattern":"^[a-z][a-z0-9_:-]{2,127}$","title":"Workflow Id","type":"string"}},"required":["workflow_id","aggregate_id","operation","status"],"title":"WorkflowView","type":"object"}
```

### `WorkspaceAnalyticsView`

```json
{"additionalProperties":false,"properties":{"current_state":{"additionalProperties":{"type":"integer"},"title":"Current State","type":"object"},"daily_events":{"items":{"additionalProperties":true,"type":"object"},"title":"Daily Events","type":"array"},"funnel":{"additionalProperties":{"type":"integer"},"title":"Funnel","type":"object"},"generated_at":{"title":"Generated At","type":"string"},"measurement_label":{"const":"OBSERVATIONAL_NOT_CAUSAL","title":"Measurement Label","type":"string"},"window_days":{"maximum":90.0,"minimum":1.0,"title":"Window Days","type":"integer"},"workspace":{"enum":["BUYER","SELLER"],"title":"Workspace","type":"string"}},"required":["workspace","window_days","generated_at","measurement_label","funnel","current_state","daily_events"],"title":"WorkspaceAnalyticsView","type":"object"}
```

### `WorkspaceChatCreate`

```json
{"properties":{"conversation_id":{"anyOf":[{"pattern":"^(?:wc_[a-f0-9]{32}|msn_[a-f0-9]{32})$","type":"string"},{"type":"null"}],"title":"Conversation Id"},"history":{"items":{"$ref":"#/components/schemas/WorkspaceMessage"},"maxItems":20,"title":"History","type":"array"},"message":{"maxLength":8000,"minLength":1,"title":"Message","type":"string"},"mission_id":{"anyOf":[{"pattern":"^msn_[a-f0-9]{32}$","type":"string"},{"type":"null"}],"title":"Mission Id"},"mode":{"default":"sira","enum":["sira","seil"],"title":"Mode","type":"string"}},"required":["message"],"title":"WorkspaceChatCreate","type":"object"}
```

### `WorkspaceChatView`

```json
{"properties":{"advisory_only":{"default":false,"title":"Advisory Only","type":"boolean"},"artifacts":{"items":{"$ref":"#/components/schemas/MissionArtifactView"},"title":"Artifacts","type":"array"},"attention":{"anyOf":[{"$ref":"#/components/schemas/AttentionView"},{"type":"null"}]},"conversation_id":{"title":"Conversation Id","type":"string"},"events":{"items":{"$ref":"#/components/schemas/MissionEventView"},"title":"Events","type":"array"},"follow_up_required":{"default":false,"title":"Follow Up Required","type":"boolean"},"message":{"title":"Message","type":"string"},"mission":{"$ref":"#/components/schemas/MissionSummaryView"},"mission_id":{"title":"Mission Id","type":"string"},"panel":{"anyOf":[{"enum":["catalog","connectors","decisions","inbox"],"type":"string"},{"type":"null"}],"title":"Panel"},"products":{"items":{"$ref":"#/components/schemas/CatalogProductView"},"title":"Products","type":"array"},"proposals":{"items":{"$ref":"#/components/schemas/AgentProposalView"},"title":"Proposals","type":"array"},"tool_calls":{"items":{"type":"string"},"title":"Tool Calls","type":"array"}},"required":["conversation_id","mission_id","message","mission"],"title":"WorkspaceChatView","type":"object"}
```

### `WorkspaceConversationView`

```json
{"properties":{"artifacts":{"items":{"$ref":"#/components/schemas/MissionArtifactView"},"title":"Artifacts","type":"array"},"events":{"items":{"$ref":"#/components/schemas/MissionEventView"},"title":"Events","type":"array"},"id":{"title":"Id","type":"string"},"messages":{"items":{"$ref":"#/components/schemas/WorkspaceMessage"},"title":"Messages","type":"array"},"mission":{"$ref":"#/components/schemas/MissionSummaryView"},"mode":{"enum":["sira","seil"],"title":"Mode","type":"string"},"open_tasks":{"items":{"additionalProperties":true,"type":"object"},"title":"Open Tasks","type":"array"},"title":{"title":"Title","type":"string"},"updated_at":{"title":"Updated At","type":"string"}},"required":["id","mode","title","messages","updated_at","mission"],"title":"WorkspaceConversationView","type":"object"}
```

### `WorkspaceMessage`

```json
{"properties":{"content":{"maxLength":12000,"minLength":1,"title":"Content","type":"string"},"proposals":{"items":{"$ref":"#/components/schemas/AgentProposalView"},"title":"Proposals","type":"array"},"role":{"enum":["user","assistant"],"title":"Role","type":"string"},"tool_calls":{"items":{"type":"string"},"title":"Tool Calls","type":"array"}},"required":["role","content"],"title":"WorkspaceMessage","type":"object"}
```

### `WorkspaceSettingsUpdate`

```json
{"additionalProperties":false,"properties":{"change_reason":{"maxLength":500,"minLength":3,"title":"Change Reason","type":"string"},"disclosure_defaults":{"$ref":"#/components/schemas/DisclosureDefaults"},"notification_channels":{"$ref":"#/components/schemas/NotificationChannels"},"quiet_hours":{"$ref":"#/components/schemas/QuietHours"}},"required":["notification_channels","quiet_hours","disclosure_defaults","change_reason"],"title":"WorkspaceSettingsUpdate","type":"object"}
```

### `WorkspaceSettingsView`

```json
{"additionalProperties":false,"properties":{"consent_boundary":{"const":"BILATERAL_EXACT_FIELD_MATCH_REQUIRED","title":"Consent Boundary","type":"string"},"current_hash":{"title":"Current Hash","type":"string"},"current_version":{"minimum":0.0,"title":"Current Version","type":"integer"},"disclosure_defaults":{"$ref":"#/components/schemas/DisclosureDefaults"},"etag":{"title":"Etag","type":"string"},"id":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Id"},"notification_channels":{"$ref":"#/components/schemas/NotificationChannels"},"party":{"enum":["BUYER","SELLER"],"title":"Party","type":"string"},"persisted":{"title":"Persisted","type":"boolean"},"quiet_hours":{"$ref":"#/components/schemas/QuietHours"},"updated_at":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Updated At"}},"required":["id","party","current_version","current_hash","etag","persisted","notification_channels","quiet_hours","disclosure_defaults","consent_boundary","updated_at"],"title":"WorkspaceSettingsView","type":"object"}
```


## Appendix D. Source route map, hidden endpoints and guards

Extracted from all route decorators, including `include_in_schema=False`. Guard expressions show explicit calls in each route; router dependencies, middleware and service/repository checks still apply. This is also a cross-check against stale generated OpenAPI. Type aliases such as `ContextDependency` and `IdempotencyDependency` are defined in the corresponding source module.

### `POST /v1/exchange-cases`

Source: `services/api/sira_api/exchange_routes.py:48`; handler `create_exchange_case`.

Handler parameters: `body: ExchangeCaseCreate; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency`.

Response model: `ExchangeCaseCreated`.

Explicit guards: `require_human_identity(context)`; `require_permission(context, 'can_select_recommendation')`

### `GET /v1/exchange-cases/{case_id}`

Source: `services/api/sira_api/exchange_routes.py:72`; handler `get_exchange_case`.

Handler parameters: `case_id: str; context: ContextDependency; service: ServiceDependency; route_capability: Annotated[str, Query(alias='route', min_length=64, max_length=4096)]`.

Response model: `ExchangeProjectionView`.

Explicit guards: `require_human_identity(context)`; `require_permission(context, 'can_view_context')`

### `POST /v1/exchange-cases/{case_id}/evidence`

Source: `services/api/sira_api/exchange_routes.py:94`; handler `publish_exchange_evidence`.

Handler parameters: `case_id: str; body: ExchangeEvidencePublish; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; route_capability: Annotated[str, Query(alias='route', min_length=64, max_length=4096)]`.

Response model: `ExchangeProjectionView`.

Explicit guards: `require_human_identity(context)`; `require_permission(context, 'can_view_context')`

### `POST /v1/exchange-cases/{case_id}/offers`

Source: `services/api/sira_api/exchange_routes.py:123`; handler `propose_exchange_offer`.

Handler parameters: `case_id: str; body: ExchangeOfferCreate; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; route_capability: Annotated[str, Query(alias='route', min_length=64, max_length=4096)]`.

Response model: `ExchangeProjectionView`.

Explicit guards: `require_human_identity(context)`; `require_permission(context, 'can_view_context')`

### `POST /v1/exchange-cases/{case_id}/accept`

Source: `services/api/sira_api/exchange_routes.py:156`; handler `accept_exchange_offer`.

Handler parameters: `case_id: str; body: ExchangeOfferAccept; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; route_capability: Annotated[str, Query(alias='route', min_length=64, max_length=4096)]`.

Response model: `ExchangeProjectionView`.

Explicit guards: `require_human_identity(context)`; `require_permission(context, 'can_view_context')`

### `POST /v1/exchange-cases/{case_id}/approve`

Source: `services/api/sira_api/exchange_routes.py:184`; handler `approve_exchange_offer`.

Handler parameters: `case_id: str; body: ExchangeOfferApprove; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; route_capability: Annotated[str, Query(alias='route', min_length=64, max_length=4096)]`.

Response model: `ExchangeProjectionView`.

Explicit guards: `require_human_identity(context)`; `require_permission(context, 'can_approve_purchase', require_step_up=True)`

### `POST /v1/exchange-cases/{case_id}/handoffs`

Source: `services/api/sira_api/exchange_routes.py:214`; handler `create_exchange_handoff`.

Handler parameters: `case_id: str; body: ExchangeHandoffCreate; context: ContextDependency; service: ServiceDependency; _idempotency_key: IdempotencyDependency; route_capability: Annotated[str, Query(alias='route', min_length=64, max_length=4096)]`.

Response model: `ExchangeHandoffView`.

Explicit guards: `require_human_identity(context)`; `require_permission(context, 'can_execute_purchase', require_step_up=True)`

### `POST /v1/exchange-cases/{case_id}/handoffs/{handoff_id}/open`

Source: `services/api/sira_api/exchange_routes.py:240`; handler `open_exchange_handoff`.

Handler parameters: `case_id: str; handoff_id: str; body: ExchangeHandoffOpen; context: ContextDependency; service: ServiceDependency; _idempotency_key: IdempotencyDependency; route_capability: Annotated[str, Query(alias='route', min_length=64, max_length=4096)]`.

Response model: `ExchangeHandoffView`.

Explicit guards: `require_human_identity(context)`; `require_permission(context, 'can_execute_purchase', require_step_up=True)`

### `GET /v1/qualification/settings`

Source: `services/api/sira_api/qualification_routes.py:81`; handler `get_workspace_settings`.

Handler parameters: `response: Response; context: ContextDependency; service: ServiceDependency`.

Response model: `WorkspaceSettingsView`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `PUT /v1/qualification/settings`

Source: `services/api/sira_api/qualification_routes.py:102`; handler `update_workspace_settings`.

Handler parameters: `body: WorkspaceSettingsUpdate; response: Response; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; if_match: IfMatchDependency`.

Response model: `QualificationMutationView`.

Explicit guards: `require_human_identity(context)`; `require_permission(context, 'can_view_context')`

### `GET /v1/qualification/analytics`

Source: `services/api/sira_api/qualification_routes.py:131`; handler `get_workspace_analytics`.

Handler parameters: `context: ContextDependency; service: ServiceDependency; days: Annotated[int, Query(ge=1, le=90)]`.

Response model: `WorkspaceAnalyticsView`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `GET /v1/qualification/inbox`

Source: `services/api/sira_api/qualification_routes.py:151`; handler `get_qualification_inbox`.

Handler parameters: `context: ContextDependency; service: ServiceDependency; limit: Annotated[int, Query(ge=1, le=100)]`.

Response model: `QualificationInboxView`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `GET /v1/qualification/marketplace/search`

Source: `services/api/sira_api/qualification_routes.py:177`; handler `search_qualification_marketplace`.

Handler parameters: `context: ContextDependency; service: ServiceDependency; category: Annotated[str, Query(min_length=3, max_length=80)]; query: Annotated[str, Query(min_length=3, max_length=1000)]; limit: Annotated[int, Query(ge=1, le=30)]`.

Response model: `PublicMarketplaceSearchView`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `GET /v1/qualification/marketplace/products/{product_id}`

Source: `services/api/sira_api/qualification_routes.py:200`; handler `get_qualification_marketplace_product`.

Handler parameters: `product_id: str; context: ContextDependency; service: ServiceDependency`.

Response model: `PublicMarketplaceProductView`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `GET /v1/qualification/company-context`

Source: `services/api/sira_api/qualification_routes.py:216`; handler `list_company_context`.

Handler parameters: `context: ContextDependency; service: ServiceDependency; include_retired: bool`.

Response model: `CompanyContextList`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `GET /v1/qualification/company-context/{item_id}`

Source: `services/api/sira_api/qualification_routes.py:234`; handler `get_company_context`.

Handler parameters: `item_id: str; response: Response; context: ContextDependency; service: ServiceDependency`.

Response model: `CompanyContextView`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `POST /v1/qualification/company-context`

Source: `services/api/sira_api/qualification_routes.py:256`; handler `create_company_context`.

Handler parameters: `body: CompanyContextCreate; response: Response; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency`.

Response model: `QualificationMutationView`.

Explicit guards: `require_human_identity(context)`; `require_permission(context, 'can_manage_procurement_gate')`

### `PUT /v1/qualification/company-context/{item_id}`

Source: `services/api/sira_api/qualification_routes.py:283`; handler `update_company_context`.

Handler parameters: `item_id: str; body: CompanyContextUpdate; response: Response; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; if_match: IfMatchDependency`.

Response model: `QualificationMutationView`.

Explicit guards: `require_human_identity(context)`; `require_permission(context, 'can_manage_procurement_gate')`

### `POST /v1/qualification/company-context/{item_id}/retire`

Source: `services/api/sira_api/qualification_routes.py:313`; handler `retire_company_context`.

Handler parameters: `item_id: str; response: Response; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; if_match: IfMatchDependency`.

Response model: `QualificationMutationView`.

Explicit guards: `require_human_identity(context)`; `require_permission(context, 'can_manage_procurement_gate')`

### `POST /v1/qualification/missions`

Source: `services/api/sira_api/qualification_routes.py:342`; handler `create_qualification_mission`.

Handler parameters: `body: QualificationMissionCreate; response: Response; request: Request; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency`.

Response model: `QualificationMutationView`.

Explicit guards: `require_human_identity(context)`; `require_permission(context, 'can_submit_request')`

### `GET /v1/qualification/missions/{mission_id}`

Source: `services/api/sira_api/qualification_routes.py:371`; handler `get_qualification_mission`.

Handler parameters: `mission_id: str; response: Response; context: ContextDependency; service: ServiceDependency`.

Response model: `QualificationMissionView`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `GET /v1/qualification/missions/{mission_id}/events`

Source: `services/api/sira_api/qualification_routes.py:392`; handler `get_qualification_mission_events`.

Handler parameters: `mission_id: str; context: ContextDependency; service: ServiceDependency; after: Annotated[str &#124; None, Query(max_length=64)]; limit: Annotated[int, Query(ge=1, le=100)]`.

Response model: `QualificationEventFeed`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `POST /v1/qualification/decisions/{decision_id}/approval`

Source: `services/api/sira_api/qualification_routes.py:412`; handler `decide_qualification_approval`.

Handler parameters: `decision_id: str; body: QualificationApprovalCreate; response: Response; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; if_match: IfMatchDependency`.

Response model: `QualificationMutationView`.

Explicit guards: `require_human_identity(context)`; `require_permission(context, 'can_approve_purchase', require_step_up=True)`

### `GET /v1/qualification/engagements/{engagement_id}`

Source: `services/api/sira_api/qualification_routes.py:443`; handler `get_qualification_engagement`.

Handler parameters: `engagement_id: str; response: Response; context: ContextDependency; service: ServiceDependency`.

Response model: `QualificationEngagementView`.

Explicit guards: No direct require_* call; inspect dependency and service guards.

### `POST /v1/qualification/engagements/{engagement_id}/responses`

Source: `services/api/sira_api/qualification_routes.py:463`; handler `record_qualification_seller_response`.

Handler parameters: `engagement_id: str; body: QualificationSellerResponseCreate; response: Response; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; if_match: IfMatchDependency`.

Response model: `QualificationMutationView`.

Explicit guards: `require_human_identity(context)`

### `POST /v1/qualification/engagements/{engagement_id}/consents`

Source: `services/api/sira_api/qualification_routes.py:499`; handler `record_qualification_consent`.

Handler parameters: `engagement_id: str; body: QualificationConsentCreate; response: Response; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; if_match: IfMatchDependency`.

Response model: `QualificationMutationView`.

Explicit guards: `require_human_identity(context)`

### `POST /v1/qualification/engagements/{engagement_id}/introduction`

Source: `services/api/sira_api/qualification_routes.py:536`; handler `create_qualification_introduction`.

Handler parameters: `engagement_id: str; body: QualificationIntroductionCreate; response: Response; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; if_match: IfMatchDependency`.

Response model: `QualificationMutationView`.

Explicit guards: `require_human_identity(context)`; `require_permission(context, 'can_approve_purchase', require_step_up=True)`

### `GET /v1/qualification/missions/{mission_id}/integrity`

Source: `services/api/sira_api/qualification_routes.py:566`; handler `get_qualification_integrity`.

Handler parameters: `mission_id: str; context: ContextDependency; service: ServiceDependency`.

Response model: `QualificationIntegrityView`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `GET /health`

Source: `services/api/sira_api/routes.py:72`; handler `health`.

Handler parameters: `request: Request`.

Response model: `HealthResponse`.

Explicit guards: No direct require_* call; inspect dependency and service guards.

### `GET /ready`

Source: `services/api/sira_api/routes.py:96`; handler `ready`.

Handler parameters: `request: Request; response: Response; service: ServiceDependency`.

Response model: `HealthResponse`.

Explicit guards: No direct require_* call; inspect dependency and service guards.

### `POST /v1/demo/reset`

Source: `services/api/sira_api/routes.py:113`; handler `reset_demo`.

Handler parameters: `request: Request; context: ContextDependency; service: ServiceDependency`.

Response model: `not explicitly declared`.

Explicit guards: No direct require_* call; inspect dependency and service guards.

### `POST /v1/purchase-requests` — hidden from OpenAPI

Source: `services/api/sira_api/routes.py:137`; handler `create_purchase_request`.

Handler parameters: `body: PurchaseRequestCreate; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; response: Response`.

Response model: `PurchaseRequestView`.

Explicit guards: `require_permission(context, 'can_submit_request')`

Decorator contract: `router.post('/v1/purchase-requests', response_model=PurchaseRequestView, status_code=status.HTTP_201_CREATED, include_in_schema=False, tags=['purchase requests'])`.

### `GET /v1/purchase-requests/{request_id}` — hidden from OpenAPI

Source: `services/api/sira_api/routes.py:161`; handler `get_purchase_request`.

Handler parameters: `request_id: str; context: ContextDependency; service: ServiceDependency`.

Response model: `PurchaseRequestView`.

Explicit guards: `require_permission(context, 'can_view_context')`

Decorator contract: `router.get('/v1/purchase-requests/{request_id}', response_model=PurchaseRequestView, include_in_schema=False, tags=['purchase requests'])`.

### `POST /v1/purchase-requests/{request_id}/discover` — hidden from OpenAPI

Source: `services/api/sira_api/routes.py:175`; handler `discover`.

Handler parameters: `request_id: str; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency`.

Response model: `WorkflowAccepted`.

Explicit guards: `require_permission(context, 'can_view_context')`

Decorator contract: `router.post('/v1/purchase-requests/{request_id}/discover', response_model=WorkflowAccepted, status_code=status.HTTP_202_ACCEPTED, include_in_schema=False, tags=['decisions'])`.

### `GET /v1/purchase-requests/{request_id}/decision-view` — hidden from OpenAPI

Source: `services/api/sira_api/routes.py:196`; handler `get_decision_view`.

Handler parameters: `request_id: str; context: ContextDependency; service: ServiceDependency`.

Response model: `CurrentDecisionView`.

Explicit guards: `require_permission(context, 'can_view_context')`

Decorator contract: `router.get('/v1/purchase-requests/{request_id}/decision-view', response_model=CurrentDecisionView, include_in_schema=False, tags=['decisions'])`.

### `GET /v1/purchase-requests/{request_id}/purchase-brief` — hidden from OpenAPI

Source: `services/api/sira_api/routes.py:209`; handler `get_purchase_brief`.

Handler parameters: `request_id: str; context: ContextDependency; service: ServiceDependency`.

Response model: `PurchaseBriefView`.

Explicit guards: `require_permission(context, 'can_view_context')`

Decorator contract: `router.get('/v1/purchase-requests/{request_id}/purchase-brief', response_model=PurchaseBriefView, include_in_schema=False, tags=['purchase requests'])`.

### `GET /v1/requirement-briefs/{brief_id}`

Source: `services/api/sira_api/routes.py:221`; handler `get_requirement_brief`.

Handler parameters: `brief_id: str; context: ContextDependency; service: ServiceDependency`.

Response model: `RequirementBriefView`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `POST /v1/purchase-requests/{request_id}/calibration-runs` — hidden from OpenAPI

Source: `services/api/sira_api/routes.py:241`; handler `run_calibration`.

Handler parameters: `request_id: str; body: CalibrationRunCreate; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; response: Response`.

Response model: `CalibrationRunView`.

Explicit guards: `require_permission(context, 'can_select_recommendation')`

Decorator contract: `router.post('/v1/purchase-requests/{request_id}/calibration-runs', response_model=CalibrationRunView, status_code=status.HTTP_201_CREATED, include_in_schema=False, tags=['decisions'])`.

### `POST /v1/purchase-requests/{request_id}/candidates/{candidate_id}/actions` — hidden from OpenAPI

Source: `services/api/sira_api/routes.py:268`; handler `candidate_action`.

Handler parameters: `request_id: str; candidate_id: str; body: CandidateActionCreate; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; response: Response`.

Response model: `CandidateActionView`.

Explicit guards: `require_permission(context, 'can_select_recommendation')`

Decorator contract: `router.post('/v1/purchase-requests/{request_id}/candidates/{candidate_id}/actions', response_model=CandidateActionView, status_code=status.HTTP_201_CREATED, include_in_schema=False, tags=['seller engagement'])`.

### `POST /v1/engagements/{engagement_id}/consent`

Source: `services/api/sira_api/routes.py:296`; handler `record_consent`.

Handler parameters: `engagement_id: str; body: ConsentCreate; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; response: Response`.

Response model: `EngagementView`.

Explicit guards: No direct require_* call; inspect dependency and service guards.

### `GET /v1/decisions/{decision_id}` — hidden from OpenAPI

Source: `services/api/sira_api/routes.py:322`; handler `get_decision`.

Handler parameters: `decision_id: str; context: ContextDependency; service: ServiceDependency`.

Response model: `DecisionLedgerView`.

Explicit guards: `require_permission(context, 'can_view_context')`

Decorator contract: `router.get('/v1/decisions/{decision_id}', response_model=DecisionLedgerView, tags=['decisions'], include_in_schema=False)`.

### `GET /v1/decisions/{decision_id}/counterfactuals`

Source: `services/api/sira_api/routes.py:334`; handler `get_counterfactuals`.

Handler parameters: `decision_id: str; context: ContextDependency; service: ServiceDependency`.

Response model: `CounterfactualView`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `POST /v1/decisions/{decision_id}/simulations`

Source: `services/api/sira_api/routes.py:347`; handler `simulate_decision`.

Handler parameters: `decision_id: str; body: DecisionSimulationCreate; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; response: Response`.

Response model: `DecisionSimulationView`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `POST /v1/evaluation-runs/{evaluation_run_id}/replay`

Source: `services/api/sira_api/routes.py:372`; handler `replay_evaluation`.

Handler parameters: `evaluation_run_id: str; context: ContextDependency; service: ServiceDependency`.

Response model: `EvaluationReplayView`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `POST /v1/purchase-briefs/{brief_id}/proposals/{proposal_id}/accept` — hidden from OpenAPI

Source: `services/api/sira_api/routes.py:387`; handler `accept_proposal`.

Handler parameters: `brief_id: str; proposal_id: str; body: ProposalDecisionCreate; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; response: Response`.

Response model: `ProposalDecisionView`.

Explicit guards: `require_permission(context, 'can_select_recommendation')`

Decorator contract: `router.post('/v1/purchase-briefs/{brief_id}/proposals/{proposal_id}/accept', response_model=ProposalDecisionView, include_in_schema=False, tags=['decisions'])`.

### `POST /v1/purchase-briefs/{brief_id}/proposals/{proposal_id}/reject` — hidden from OpenAPI

Source: `services/api/sira_api/routes.py:418`; handler `reject_proposal`.

Handler parameters: `brief_id: str; proposal_id: str; body: ProposalDecisionCreate; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; response: Response`.

Response model: `ProposalDecisionView`.

Explicit guards: `require_permission(context, 'can_select_recommendation')`

Decorator contract: `router.post('/v1/purchase-briefs/{brief_id}/proposals/{proposal_id}/reject', response_model=ProposalDecisionView, include_in_schema=False, tags=['decisions'])`.

### `POST /v1/decisions/{decision_id}/purchase-intents`

Source: `services/api/sira_api/routes.py:449`; handler `lock_purchase_intent`.

Handler parameters: `decision_id: str; body: PurchaseIntentCreate; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; response: Response`.

Response model: `PurchaseIntentView`.

Explicit guards: `require_permission(context, 'can_select_recommendation')`

### `POST /v1/purchase-intents/{intent_id}/approval-requests`

Source: `services/api/sira_api/routes.py:475`; handler `create_approval_request`.

Handler parameters: `intent_id: str; body: ApprovalRequestCreate; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; response: Response`.

Response model: `ApprovalRequestView`.

Explicit guards: `require_permission(context, 'can_manage_procurement_gate')`

### `POST /v1/purchase-intents/{intent_id}/payment-handoff`

Source: `services/api/sira_api/routes.py:501`; handler `create_payment_handoff`.

Handler parameters: `intent_id: str; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; response: Response`.

Response model: `PaymentHandoffView`.

Explicit guards: `require_human_identity(context)`; `require_permission(context, 'can_execute_purchase', require_step_up=True)`

### `POST /v1/payment-handoffs/{handoff_id}/open`

Source: `services/api/sira_api/routes.py:525`; handler `open_payment_handoff`.

Handler parameters: `handoff_id: str; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency`.

Response model: `PaymentHandoffView`.

Explicit guards: `require_human_identity(context)`; `require_permission(context, 'can_execute_purchase', require_step_up=True)`

### `POST /v1/approval-requests/{approval_id}/approve`

Source: `services/api/sira_api/routes.py:546`; handler `approve`.

Handler parameters: `approval_id: str; body: ApprovalCreate; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; response: Response`.

Response model: `ApprovalRequestView`.

Explicit guards: `require_human_identity(context)`; `require_permission(context, 'can_approve_purchase')`

### `POST /v1/approval-requests/{approval_id}/reject`

Source: `services/api/sira_api/routes.py:574`; handler `reject_approval`.

Handler parameters: `approval_id: str; body: ApprovalRejectCreate; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; response: Response`.

Response model: `ApprovalRequestView`.

Explicit guards: `require_human_identity(context)`; `require_permission(context, 'can_approve_purchase')`

### `POST /v1/approval-requests/{approval_id}/revoke`

Source: `services/api/sira_api/routes.py:602`; handler `revoke_approval`.

Handler parameters: `approval_id: str; body: ApprovalRevokeCreate; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; response: Response`.

Response model: `ApprovalRequestView`.

Explicit guards: `require_human_identity(context)`; `require_permission(context, 'can_approve_purchase')`

### `GET /v1/purchase-intents/{intent_id}/status`

Source: `services/api/sira_api/routes.py:630`; handler `purchase_status`.

Handler parameters: `intent_id: str; context: ContextDependency; service: ServiceDependency`.

Response model: `PurchaseStatusView`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `POST /v1/purchase-intents/{intent_id}/outcome-checkpoints`

Source: `services/api/sira_api/routes.py:643`; handler `record_purchase_outcome`.

Handler parameters: `intent_id: str; body: OutcomeCheckpointCreate; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; response: Response`.

Response model: `OutcomeCheckpointView`.

Explicit guards: `require_human_identity(context)`; `require_permission(context, 'can_select_recommendation')`

### `GET /v1/organizations/{organization_id}/stackfile`

Source: `services/api/sira_api/routes.py:669`; handler `get_stackfile`.

Handler parameters: `organization_id: str; context: ContextDependency; service: ServiceDependency`.

Response model: `StackfileView`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `GET /v1/workflows/{workflow_id}`

Source: `services/api/sira_api/routes.py:683`; handler `get_workflow`.

Handler parameters: `workflow_id: str; context: ContextDependency; service: ServiceDependency`.

Response model: `WorkflowView`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `GET /v1/workflows/{workflow_id}/events`

Source: `services/api/sira_api/routes.py:701`; handler `get_workflow_events`.

Handler parameters: `workflow_id: str; context: ContextDependency; service: ServiceDependency`.

Response model: `not explicitly declared`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `GET /v1/decision-requests`

Source: `services/api/sira_api/routes_v2.py:53`; handler `list_decision_requests`.

Handler parameters: `context: ContextDependency; service: ServiceDependency`.

Response model: `DecisionIndexView`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `POST /v1/decision-requests`

Source: `services/api/sira_api/routes_v2.py:70`; handler `create_decision_request`.

Handler parameters: `body: DecisionRequestCreate; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; response: Response`.

Response model: `DecisionRequestView`.

Explicit guards: `require_permission(context, 'can_submit_request')`

### `GET /v1/decision-requests/{request_id}`

Source: `services/api/sira_api/routes_v2.py:95`; handler `get_decision_request`.

Handler parameters: `request_id: str; context: ContextDependency; service: ServiceDependency`.

Response model: `DecisionRequestView`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `POST /v1/decision-requests/{request_id}/discover`

Source: `services/api/sira_api/routes_v2.py:113`; handler `discover_decision_request`.

Handler parameters: `request_id: str; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency`.

Response model: `WorkflowAccepted`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `GET /v1/decision-requests/{request_id}/decision-view`

Source: `services/api/sira_api/routes_v2.py:133`; handler `get_decision_room`.

Handler parameters: `request_id: str; context: ContextDependency; service: ServiceDependency; decision_version: Annotated[int &#124; None, Query(alias='version', ge=1)]`.

Response model: `DecisionView`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `GET /v1/decision-requests/{request_id}/decision-rules`

Source: `services/api/sira_api/routes_v2.py:154`; handler `get_decision_rules`.

Handler parameters: `request_id: str; context: ContextDependency; service: ServiceDependency`.

Response model: `DecisionRulesView`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `POST /v1/decision-requests/{request_id}/calibration-runs`

Source: `services/api/sira_api/routes_v2.py:170`; handler `run_decision_calibration`.

Handler parameters: `request_id: str; body: CalibrationRunCreate; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; response: Response`.

Response model: `CalibrationRunView`.

Explicit guards: `require_permission(context, 'can_select_recommendation')`

### `POST /v1/decision-requests/{request_id}/solution-options/{solution_plan_id}/actions`

Source: `services/api/sira_api/routes_v2.py:196`; handler `record_solution_option_feedback`.

Handler parameters: `request_id: str; solution_plan_id: str; body: OptionFeedbackCreate; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; response: Response`.

Response model: `OptionFeedbackView`.

Explicit guards: `require_permission(context, 'can_select_recommendation')`

### `POST /v1/decision-rules/{rules_id}/proposals/{proposal_id}/accept`

Source: `services/api/sira_api/routes_v2.py:224`; handler `accept_rule_proposal`.

Handler parameters: `rules_id: str; proposal_id: str; body: ProposalDecisionCreate; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; response: Response`.

Response model: `ProposalDecisionView`.

Explicit guards: `require_human_identity(context)`; `require_permission(context, 'can_select_recommendation')`

### `POST /v1/decision-rules/{rules_id}/proposals/{proposal_id}/reject`

Source: `services/api/sira_api/routes_v2.py:255`; handler `reject_rule_proposal`.

Handler parameters: `rules_id: str; proposal_id: str; body: ProposalDecisionCreate; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; response: Response`.

Response model: `ProposalDecisionView`.

Explicit guards: `require_human_identity(context)`; `require_permission(context, 'can_select_recommendation')`

### `GET /v1/decisions/{decision_id}`

Source: `services/api/sira_api/routes_v2.py:286`; handler `get_decision_ledger_v2`.

Handler parameters: `decision_id: str; context: ContextDependency; service: ServiceDependency`.

Response model: `DecisionLedgerV2`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `POST /v1/decisions/{decision_id}/plan-selections`

Source: `services/api/sira_api/routes_v2.py:299`; handler `select_action_plan`.

Handler parameters: `decision_id: str; body: PlanSelectionCreate; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; response: Response`.

Response model: `PlanSelectionView`.

Explicit guards: `require_human_identity(context)`; `require_permission(context, 'can_select_recommendation', require_step_up=True)`

### `POST /v1/decisions/{decision_id}/action-runs`

Source: `services/api/sira_api/routes_v2.py:328`; handler `start_action_run`.

Handler parameters: `decision_id: str; body: ActionRunCreate; context: ContextDependency; service: ServiceDependency; idempotency_key: IdempotencyDependency; response: Response`.

Response model: `ActionRunView`.

Explicit guards: `require_human_identity(context)`; `require_permission(context, 'can_select_recommendation')`

### `GET /v1/action-runs/{action_run_id}`

Source: `services/api/sira_api/routes_v2.py:356`; handler `get_action_run`.

Handler parameters: `action_run_id: str; context: ContextDependency; service: ServiceDependency`.

Response model: `ActionRunView`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `GET /v1/seller/products/search`

Source: `services/api/sira_api/seller_routes.py:107`; handler `search_seller_products`.

Handler parameters: `context: ContextDependency; service: SellerServiceDependency; query: Annotated[str &#124; None, Query(alias='q', min_length=2, max_length=200)]`.

Response model: `SellerProductSearchView`.

Explicit guards: No direct require_* call; inspect dependency and service guards.

### `POST /v1/seller/products/{product_id}/claim`

Source: `services/api/sira_api/seller_routes.py:127`; handler `claim_seller_product`.

Handler parameters: `product_id: str; body: SellerClaimCreate; response: Response; context: ContextDependency; service: SellerServiceDependency; idempotency_key: IdempotencyDependency`.

Response model: `SellerClaimView`.

Explicit guards: No direct require_* call; inspect dependency and service guards.

### `GET /v1/seller/products/{product_id}/view`

Source: `services/api/sira_api/seller_routes.py:154`; handler `get_seller_product_view`.

Handler parameters: `product_id: str; context: ContextDependency; service: SellerServiceDependency`.

Response model: `SellerEvidenceView`.

Explicit guards: No direct require_* call; inspect dependency and service guards.

### `GET /v1/seller/pack-drafts/{draft_id}`

Source: `services/api/sira_api/seller_routes.py:173`; handler `get_seller_pack_draft`.

Handler parameters: `draft_id: str; context: ContextDependency; service: SellerServiceDependency`.

Response model: `SellerPackDraftView`.

Explicit guards: No direct require_* call; inspect dependency and service guards.

### `PATCH /v1/seller/pack-drafts/{draft_id}`

Source: `services/api/sira_api/seller_routes.py:192`; handler `patch_seller_pack_draft`.

Handler parameters: `draft_id: str; body: SellerPackDraftPatch; response: Response; context: ContextDependency; service: SellerServiceDependency; idempotency_key: IdempotencyDependency`.

Response model: `SellerPackDraftView`.

Explicit guards: No direct require_* call; inspect dependency and service guards.

### `POST /v1/seller/pack-drafts/{draft_id}/evidence`

Source: `services/api/sira_api/seller_routes.py:221`; handler `attach_seller_evidence`.

Handler parameters: `draft_id: str; body: SellerEvidenceAttachCreate; response: Response; context: ContextDependency; service: SellerServiceDependency; idempotency_key: IdempotencyDependency`.

Response model: `SellerEvidenceAttachmentView`.

Explicit guards: No direct require_* call; inspect dependency and service guards.

### `POST /v1/seller/pack-drafts/{draft_id}/evidence/upload`

Source: `services/api/sira_api/seller_routes.py:249`; handler `upload_seller_evidence`.

Handler parameters: `draft_id: str; response: Response; context: ContextDependency; service: SellerServiceDependency; idempotency_key: IdempotencyDependency; evidence_file: Annotated[UploadFile, File(description='Private source evidence, max 25 MiB')]; source_class: Annotated[str, Form(min_length=2, max_length=80)]; claim_fields_json: Annotated[str, Form(min_length=4, max_length=2000)]; observed_at: Annotated[datetime &#124; None, Form()]`.

Response model: `SellerEvidenceAttachmentView`.

Explicit guards: No direct require_* call; inspect dependency and service guards.

### `POST /v1/seller/pack-drafts/{draft_id}/submit-review`

Source: `services/api/sira_api/seller_routes.py:307`; handler `submit_seller_pack_review`.

Handler parameters: `draft_id: str; body: SellerSubmitReviewCreate; response: Response; context: ContextDependency; service: SellerServiceDependency; idempotency_key: IdempotencyDependency`.

Response model: `SellerPackDraftView`.

Explicit guards: No direct require_* call; inspect dependency and service guards.

### `POST /v1/seller/pack-drafts/{draft_id}/review-decisions`

Source: `services/api/sira_api/seller_routes.py:335`; handler `record_seller_review_decision`.

Handler parameters: `draft_id: str; body: SellerReviewDecisionCreate; response: Response; context: ContextDependency; service: SellerServiceDependency; idempotency_key: IdempotencyDependency`.

Response model: `SellerReviewDecisionView`.

Explicit guards: No direct require_* call; inspect dependency and service guards.

### `POST /v1/seller/pack-drafts/{draft_id}/publish`

Source: `services/api/sira_api/seller_routes.py:363`; handler `publish_seller_pack`.

Handler parameters: `draft_id: str; body: SellerPublishCreate; response: Response; context: ContextDependency; service: SellerServiceDependency; idempotency_key: IdempotencyDependency`.

Response model: `SellerPackVersionView`.

Explicit guards: No direct require_* call; inspect dependency and service guards.

### `POST /v1/seller/pack-versions/{version_id}/suspend`

Source: `services/api/sira_api/seller_routes.py:391`; handler `suspend_seller_pack`.

Handler parameters: `version_id: str; body: SellerSuspendCreate; response: Response; context: ContextDependency; service: SellerServiceDependency; idempotency_key: IdempotencyDependency`.

Response model: `SellerPackVersionView`.

Explicit guards: No direct require_* call; inspect dependency and service guards.

### `GET /v1/seller/pack-versions/{version_id}/exports`

Source: `services/api/sira_api/seller_routes.py:419`; handler `get_seller_pack_exports`.

Handler parameters: `version_id: str; context: ContextDependency; service: SellerServiceDependency`.

Response model: `SellerPackExportsView`.

Explicit guards: No direct require_* call; inspect dependency and service guards.

### `GET /v1/seller/products/{product_id}/activity-metrics`

Source: `services/api/sira_api/seller_routes.py:438`; handler `get_seller_activity_metrics`.

Handler parameters: `product_id: str; context: ContextDependency; service: SellerServiceDependency`.

Response model: `SellerActivityMetrics`.

Explicit guards: No direct require_* call; inspect dependency and service guards.

### `GET /v1/capabilities`

Source: `services/api/sira_api/workspace_routes.py:53`; handler `workspace_capabilities`.

Handler parameters: `context: ContextDependency; service: ServiceDependency`.

Response model: `list[CapabilityView]`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `POST /v1/workspace/chat`

Source: `services/api/sira_api/workspace_routes.py:61`; handler `workspace_chat`.

Handler parameters: `body: WorkspaceChatCreate; request: Request; context: ContextDependency; service: ServiceDependency`.

Response model: `WorkspaceChatView`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `GET /v1/workspace/conversations`

Source: `services/api/sira_api/workspace_routes.py:94`; handler `workspace_conversations`.

Handler parameters: `mode: Literal['sira', 'seil']; request: Request; context: ContextDependency; service: ServiceDependency`.

Response model: `list[WorkspaceConversationView]`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `GET /v1/workspace/missions/{mission_id}`

Source: `services/api/sira_api/workspace_routes.py:119`; handler `workspace_mission`.

Handler parameters: `mission_id: str; request: Request; context: ContextDependency; service: ServiceDependency`.

Response model: `MissionSnapshotView`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `GET /v1/workspace/catalog`

Source: `services/api/sira_api/workspace_routes.py:135`; handler `workspace_catalog`.

Handler parameters: `context: ContextDependency; service: ServiceDependency`.

Response model: `list[CatalogProductView]`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `GET /v1/workspace/catalog/{product_id}`

Source: `services/api/sira_api/workspace_routes.py:145`; handler `workspace_product`.

Handler parameters: `product_id: str; context: ContextDependency; service: ServiceDependency`.

Response model: `CatalogProductView`.

Explicit guards: `require_permission(context, 'can_view_context')`

### `GET /v1/workspace/connectors`

Source: `services/api/sira_api/workspace_routes.py:162`; handler `workspace_connectors`.

Handler parameters: `context: ContextDependency; service: ServiceDependency`.

Response model: `list[ConnectorView]`.

Explicit guards: `require_permission(context, 'can_view_context')`

Cross-check: 91 source operations; 10 hidden route declarations. Published operations missing from these route files: `[]`. Source-only operations: `[('/v1/purchase-briefs/{brief_id}/proposals/{proposal_id}/accept', 'post'), ('/v1/purchase-briefs/{brief_id}/proposals/{proposal_id}/reject', 'post'), ('/v1/purchase-requests', 'post'), ('/v1/purchase-requests/{request_id}', 'get'), ('/v1/purchase-requests/{request_id}/calibration-runs', 'post'), ('/v1/purchase-requests/{request_id}/candidates/{candidate_id}/actions', 'post'), ('/v1/purchase-requests/{request_id}/decision-view', 'get'), ('/v1/purchase-requests/{request_id}/discover', 'post'), ('/v1/purchase-requests/{request_id}/purchase-brief', 'get')]`.


## Appendix E. Complete ORM database field and constraint dictionary

`Mapped[...]` states the Python type; `mapped_column(...)` records SQL type, nullability, defaults, primary/foreign keys and indexes as declared. Inherited mapped columns are expanded per table. `organization_id` from TenantOwned is an indexed non-null `String(64)` foreign key to `organizations.id` with RESTRICT deletion. `Timestamped` supplies timezone-aware created/updated timestamps with server `now()` and update behavior. JSON_DOCUMENT is JSON with JSONB variants for PostgreSQL/CockroachDB. Migration-only RLS/grants/vector DDL must also be implemented.

### `action_runs` — `ActionRun`

Source: `python/persistence/models.py:1118`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `decision_id` | `Mapped[str]` | `mapped_column(ForeignKey('decision_records.id', ondelete='RESTRICT'), nullable=False)` |
| `solution_plan_record_id` | `Mapped[str]` | `mapped_column(ForeignKey('evaluation_solution_plans.id', ondelete='RESTRICT'), nullable=False)` |
| `solution_plan_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `purchase_intent_id` | `Mapped[str &#124; None]` | `mapped_column(ForeignKey('purchase_intents.id', ondelete='RESTRICT'), nullable=True)` |
| `action` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `status` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `current_checkpoint` | `Mapped[str &#124; None]` | `mapped_column(String(100), nullable=True)` |
| `last_successful_checkpoint` | `Mapped[str &#124; None]` | `mapped_column(String(100), nullable=True)` |
| `owner_role` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `blocking_task` | `Mapped[dict[str, Any] &#124; None]` | `mapped_column(JSON_DOCUMENT, nullable=True)` |
| `recovery_action` | `Mapped[dict[str, Any] &#124; None]` | `mapped_column(JSON_DOCUMENT, nullable=True)` |
| `retryable` | `Mapped[bool]` | `mapped_column(Boolean, nullable=False, default=False)` |
| `safe_to_leave` | `Mapped[bool]` | `mapped_column(Boolean, nullable=False, default=True)` |
| `started_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |
| `completed_at` | `Mapped[datetime &#124; None]` | `mapped_column(DateTime(timezone=True), nullable=True)` |
| `run_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `supersedes_id` | `Mapped[str &#124; None]` | `mapped_column(ForeignKey('action_runs.id', ondelete='RESTRICT'), nullable=True)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'run_hash', name='uq_action_run_hash'), UniqueConstraint('organization_id', 'decision_id', 'solution_plan_record_id', name='uq_action_run_decision_plan'), CheckConstraint("action IN ('REUSE_EXISTING','CONFIGURE_EXISTING','NO_ACTION','BUY','RENEW','RESIZE','REPLACE','CONSOLIDATE','CANCEL')", name='ck_action_run_action'), CheckConstraint("status IN ('QUEUED','RUNNING','WAITING_FOR_HUMAN','RETRYABLE_ERROR','UNCERTAIN','COMPLETED','FAILED_FINAL')", name='ck_action_run_status'), CheckConstraint('completed_at IS NULL OR completed_at >= started_at', name='ck_action_run_completion_order'), CheckConstraint("status NOT IN ('COMPLETED','FAILED_FINAL') OR completed_at IS NOT NULL", name='ck_action_run_terminal_completion'), Index('ix_action_runs_decision_status', 'decision_id', 'status'))
```

### `agent_capability_grants` — `AgentCapabilityGrant`

Source: `python/persistence/models.py:2399`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `mission_id` | `Mapped[str]` | `mapped_column(ForeignKey('agent_missions.id', ondelete='CASCADE'), nullable=False)` |
| `subject_type` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `subject_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `capability` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `scope` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `status` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `granted_by` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `grant_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `max_uses` | `Mapped[int]` | `mapped_column(Integer, nullable=False, default=1)` |
| `uses` | `Mapped[int]` | `mapped_column(Integer, nullable=False, default=0)` |
| `expires_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint("subject_type IN ('ROOT_AGENT','SUBAGENT','USER','SYSTEM')", name='ck_agent_capability_subject'), CheckConstraint("status IN ('ACTIVE','REVOKED','EXPIRED','CONSUMED')", name='ck_agent_capability_status'), CheckConstraint('max_uses > 0 AND uses >= 0 AND uses <= max_uses', name='ck_agent_grant_uses'), UniqueConstraint('organization_id', 'grant_hash', name='uq_agent_capability_hash'))
```

### `agent_effects` — `AgentEffect`

Source: `python/persistence/models.py:2435`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `mission_id` | `Mapped[str]` | `mapped_column(ForeignKey('agent_missions.id', ondelete='RESTRICT'), nullable=False)` |
| `task_id` | `Mapped[str &#124; None]` | `mapped_column(ForeignKey('agent_mission_tasks.id', ondelete='SET NULL'), nullable=True)` |
| `capability_grant_id` | `Mapped[str &#124; None]` | `mapped_column(ForeignKey('agent_capability_grants.id', ondelete='RESTRICT'), nullable=True)` |
| `effect_type` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `status` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `idempotency_key` | `Mapped[str]` | `mapped_column(String(160), nullable=False)` |
| `request_payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `request_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `approval_reference` | `Mapped[str &#124; None]` | `mapped_column(String(128), nullable=True)` |
| `provider_reference` | `Mapped[str &#124; None]` | `mapped_column(String(160), nullable=True)` |
| `result_artifact_id` | `Mapped[str &#124; None]` | `mapped_column(ForeignKey('agent_mission_artifacts.id', ondelete='SET NULL'), nullable=True)` |
| `safe_error_code` | `Mapped[str &#124; None]` | `mapped_column(String(80), nullable=True)` |

Constraints/indexes:

```python
(CheckConstraint("status IN ('PROPOSED','AUTHORIZED','DISPATCHING','ACKNOWLEDGED','VERIFIED','UNCERTAIN','RECONCILING','COMPENSATING','FAILED','CANCELLED')", name='ck_agent_effect_status'), UniqueConstraint('organization_id', 'mission_id', 'idempotency_key', name='uq_agent_effect_key'))
```

### `agent_experiments` — `AgentExperiment`

Source: `python/persistence/models.py:2474`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `mission_id` | `Mapped[str]` | `mapped_column(ForeignKey('agent_missions.id', ondelete='CASCADE'), nullable=False)` |
| `task_id` | `Mapped[str &#124; None]` | `mapped_column(ForeignKey('agent_mission_tasks.id', ondelete='SET NULL'), nullable=True)` |
| `candidate_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `status` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `procedure` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `environment` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `success_signals` | `Mapped[list[dict[str, Any]]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `observations` | `Mapped[list[dict[str, Any]]]` | `mapped_column(JSON_DOCUMENT, nullable=False, default=list)` |
| `limitations` | `Mapped[list[str]]` | `mapped_column(JSON_DOCUMENT, nullable=False, default=list)` |
| `replay_spec` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `cost` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False, default=dict)` |
| `result_artifact_id` | `Mapped[str &#124; None]` | `mapped_column(ForeignKey('agent_mission_artifacts.id', ondelete='SET NULL'), nullable=True)` |
| `content_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `started_at` | `Mapped[datetime &#124; None]` | `mapped_column(DateTime(timezone=True), nullable=True)` |
| `completed_at` | `Mapped[datetime &#124; None]` | `mapped_column(DateTime(timezone=True), nullable=True)` |

Constraints/indexes:

```python
(CheckConstraint("status IN ('PLANNED','PROVISIONING','RUNNING','COMPLETED','FAILED','CANCELLED')", name='ck_agent_experiment_status'), UniqueConstraint('organization_id', 'mission_id', 'content_hash', name='uq_agent_experiment_hash'))
```

### `agent_mission_artifacts` — `AgentMissionArtifact`

Source: `python/persistence/models.py:2332`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `mission_id` | `Mapped[str]` | `mapped_column(ForeignKey('agent_missions.id', ondelete='CASCADE'), nullable=False)` |
| `task_id` | `Mapped[str &#124; None]` | `mapped_column(ForeignKey('agent_mission_tasks.id', ondelete='SET NULL'), nullable=True)` |
| `kind` | `Mapped[str]` | `mapped_column(String(48), nullable=False)` |
| `title` | `Mapped[str]` | `mapped_column(String(240), nullable=False)` |
| `status` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `authority` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `source_refs` | `Mapped[list[dict[str, Any]]]` | `mapped_column(JSON_DOCUMENT, nullable=False, default=list)` |
| `content_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `created_by` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint("status IN ('DRAFT','READY','STALE','FAILED','SUPERSEDED')", name='ck_agent_mission_artifact_status'), CheckConstraint("authority IN ('OBSERVED','VERIFIED','INFERRED','SELLER_ASSERTED','USER_ASSERTED')", name='ck_agent_mission_artifact_authority'), UniqueConstraint('organization_id', 'mission_id', 'content_hash', name='uq_agent_artifact_hash'), Index('ix_agent_mission_artifact_kind', 'organization_id', 'mission_id', 'kind'))
```

### `agent_mission_checkpoints` — `AgentMissionCheckpoint`

Source: `python/persistence/models.py:2371`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `mission_id` | `Mapped[str]` | `mapped_column(ForeignKey('agent_missions.id', ondelete='CASCADE'), nullable=False)` |
| `sequence` | `Mapped[int]` | `mapped_column(BigInteger, nullable=False)` |
| `mission_version` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `state` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `projection` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `unresolved_task_ids` | `Mapped[list[str]]` | `mapped_column(JSON_DOCUMENT, nullable=False, default=list)` |
| `content_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'mission_id', 'sequence', name='uq_agent_checkpoint_sequence'),)
```

### `agent_mission_events` — `AgentMissionEvent`

Source: `python/persistence/models.py:2266`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `mission_id` | `Mapped[str]` | `mapped_column(ForeignKey('agent_missions.id', ondelete='CASCADE'), nullable=False)` |
| `sequence` | `Mapped[int]` | `mapped_column(BigInteger, nullable=False)` |
| `event_type` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `event_key` | `Mapped[str]` | `mapped_column(String(160), nullable=False)` |
| `actor_type` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `actor_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `payload_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `occurred_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'mission_id', 'sequence', name='uq_agent_mission_event_sequence'), UniqueConstraint('organization_id', 'event_key', name='uq_agent_mission_event_key'), Index('ix_agent_mission_event_stream', 'organization_id', 'mission_id', 'sequence'))
```

### `agent_mission_tasks` — `AgentMissionTask`

Source: `python/persistence/models.py:2295`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `mission_id` | `Mapped[str]` | `mapped_column(ForeignKey('agent_missions.id', ondelete='CASCADE'), nullable=False)` |
| `parent_task_id` | `Mapped[str &#124; None]` | `mapped_column(ForeignKey('agent_mission_tasks.id', ondelete='RESTRICT'), nullable=True)` |
| `kind` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `title` | `Mapped[str]` | `mapped_column(String(240), nullable=False)` |
| `status` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `owner_type` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `assigned_role` | `Mapped[str &#124; None]` | `mapped_column(String(80), nullable=True)` |
| `input_payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `budget` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False, default=dict)` |
| `output_artifact_id` | `Mapped[str &#124; None]` | `mapped_column(String(64), nullable=True)` |
| `attempt` | `Mapped[int]` | `mapped_column(Integer, nullable=False, default=0)` |
| `safe_error_code` | `Mapped[str &#124; None]` | `mapped_column(String(80), nullable=True)` |
| `deadline_at` | `Mapped[datetime &#124; None]` | `mapped_column(DateTime(timezone=True), nullable=True)` |

Constraints/indexes:

```python
(CheckConstraint("status IN ('PENDING','RUNNING','WAITING','COMPLETED','FAILED','CANCELLED')", name='ck_agent_mission_task_status'), CheckConstraint("owner_type IN ('ROOT_AGENT','SUBAGENT','HUMAN','SYSTEM')", name='ck_agent_mission_task_owner'), Index('ix_agent_mission_task_queue', 'organization_id', 'mission_id', 'status'))
```

### `agent_missions` — `AgentMission`

Source: `python/persistence/models.py:2232`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `actor_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `mode` | `Mapped[str]` | `mapped_column(String(12), nullable=False)` |
| `goal` | `Mapped[str]` | `mapped_column(Text, nullable=False)` |
| `state` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `version` | `Mapped[int]` | `mapped_column(Integer, nullable=False, default=1)` |
| `budget` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False, default=dict)` |
| `plan` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False, default=dict)` |
| `world_model` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False, default=dict)` |
| `current_checkpoint_id` | `Mapped[str &#124; None]` | `mapped_column(String(64), nullable=True)` |
| `stop_reason` | `Mapped[str &#124; None]` | `mapped_column(String(120), nullable=True)` |
| `last_error_code` | `Mapped[str &#124; None]` | `mapped_column(String(80), nullable=True)` |

Constraints/indexes:

```python
(CheckConstraint("mode IN ('SIRA','SEIL')", name='ck_agent_mission_mode'), CheckConstraint("state IN ('CREATED','ORIENTING','PLANNING','EXPLORING','EXPERIMENTING','SYNTHESIZING','PROPOSING','AWAITING_AUTHORITY','EXECUTING','VERIFYING','MONITORING','COMPLETED','PAUSED','BLOCKED','FAILED','CANCELLED')", name='ck_agent_mission_state'), Index('ix_agent_mission_actor_state', 'organization_id', 'actor_id', 'state'))
```

### `approval_events` — `ApprovalEvent`

Source: `python/persistence/models.py:1252`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `approval_request_id` | `Mapped[str]` | `mapped_column(ForeignKey('approval_requests.id', ondelete='RESTRICT'), nullable=False)` |
| `intent_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `actor_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `actor_role` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `action` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `event_key` | `Mapped[str]` | `mapped_column(String(128), nullable=False)` |
| `reason` | `Mapped[str &#124; None]` | `mapped_column(Text, nullable=True)` |
| `occurred_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'event_key', name='uq_approval_event_key'), CheckConstraint("action IN ('APPROVE','REJECT','REVOKE','DELEGATE')", name='ck_approval_event_action'))
```

### `approval_requests` — `ApprovalRequest`

Source: `python/persistence/models.py:1227`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `purchase_intent_id` | `Mapped[str]` | `mapped_column(ForeignKey('purchase_intents.id', ondelete='RESTRICT'), nullable=False)` |
| `intent_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `policy_version` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `status` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `required_roles` | `Mapped[list[str]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `approved_roles` | `Mapped[list[str]]` | `mapped_column(JSON_DOCUMENT, nullable=False, default=list)` |
| `expires_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'purchase_intent_id', 'intent_hash', name='uq_approval_exact_intent'), CheckConstraint("status IN ('PENDING','APPROVED','REJECTED','REVOKED','EXPIRED','SUPERSEDED')", name='ck_approval_request_status'))
```

### `bilateral_exchange_cases` — `BilateralExchangeCase`

Source: `python/persistence/models.py:1942`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `seller_organization_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `state` | `Mapped[str]` | `mapped_column(String(40), nullable=False)` |
| `version` | `Mapped[int]` | `mapped_column(Integer, nullable=False, default=1)` |
| `coordinator_state` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `state_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `last_command_id` | `Mapped[str &#124; None]` | `mapped_column(String(64), nullable=True)` |

Constraints/indexes:

```python
(CheckConstraint("state IN ('CREATED','REQUIREMENT_RELEASED','EVIDENCE_RELEASED','OFFERED','COUNTERED','AGREED_PENDING_APPROVAL','APPROVED_FOR_HANDOFF','REJECTED','EXPIRED')", name='ck_bilateral_exchange_state'), Index('ix_bilateral_exchange_state', 'organization_id', 'state', 'updated_at'))
```

### `bilateral_exchange_envelopes` — `BilateralExchangeEnvelope`

Source: `python/persistence/models.py:2090`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `case_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `sender_party` | `Mapped[str]` | `mapped_column(String(12), nullable=False)` |
| `recipient_party` | `Mapped[str]` | `mapped_column(String(12), nullable=False)` |
| `sequence` | `Mapped[int]` | `mapped_column(BigInteger, nullable=False)` |
| `causation_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `manifest_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `payload_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `expires_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint("sender_party IN ('BUYER','SELLER') AND recipient_party IN ('BUYER','SELLER') AND sender_party <> recipient_party", name='ck_exchange_envelope_parties'), UniqueConstraint('organization_id', 'case_id', 'sender_party', 'sequence', name='uq_exchange_envelope_sequence'), UniqueConstraint('organization_id', 'payload_hash', name='uq_exchange_envelope_hash'), Index('ix_exchange_envelope_recipient', 'organization_id', 'case_id', 'recipient_party'))
```

### `bilateral_exchange_handoffs` — `BilateralExchangeHandoff`

Source: `python/persistence/models.py:2200`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `case_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `offer_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `approval_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `handoff_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `destination_url` | `Mapped[str]` | `mapped_column(Text, nullable=False)` |
| `recipient` | `Mapped[str]` | `mapped_column(String(200), nullable=False)` |
| `amount` | `Mapped[Decimal]` | `mapped_column(Numeric(20, 2), nullable=False)` |
| `currency` | `Mapped[str]` | `mapped_column(String(3), nullable=False)` |
| `reference` | `Mapped[str]` | `mapped_column(String(160), nullable=False)` |
| `status` | `Mapped[str]` | `mapped_column(String(16), nullable=False)` |
| `expires_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |
| `opened_at` | `Mapped[datetime &#124; None]` | `mapped_column(DateTime(timezone=True), nullable=True)` |

Constraints/indexes:

```python
(CheckConstraint("status IN ('READY','OPENED','EXPIRED','CANCELLED')", name='ck_bilateral_handoff_status'), UniqueConstraint('organization_id', 'case_id', 'offer_hash', name='uq_bilateral_handoff_offer'), UniqueConstraint('organization_id', 'handoff_hash', name='uq_bilateral_handoff_hash'), Index('ix_bilateral_handoff_case', 'organization_id', 'case_id', 'created_at'))
```

### `bilateral_exchange_receipts` — `BilateralExchangeReceipt`

Source: `python/persistence/models.py:2127`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `envelope_id` | `Mapped[str]` | `mapped_column(ForeignKey('bilateral_exchange_envelopes.id', ondelete='RESTRICT'), nullable=False)` |
| `case_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `recipient_party` | `Mapped[str]` | `mapped_column(String(12), nullable=False)` |
| `envelope_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `received_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint("recipient_party IN ('BUYER','SELLER')", name='ck_exchange_receipt_party'), UniqueConstraint('organization_id', 'envelope_id', name='uq_exchange_receipt_envelope'))
```

### `bilateral_offer_approvals` — `BilateralOfferApproval`

Source: `python/persistence/models.py:2181`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `case_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `offer_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `approver_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `approved_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |
| `expires_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |
| `approval_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'case_id', 'offer_hash', name='uq_offer_approval'), UniqueConstraint('organization_id', 'approval_hash', name='uq_offer_approval_hash'))
```

### `bilateral_offer_versions` — `BilateralOfferVersion`

Source: `python/persistence/models.py:2145`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `case_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `version` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `proposer_party` | `Mapped[str]` | `mapped_column(String(12), nullable=False)` |
| `recipient_party` | `Mapped[str]` | `mapped_column(String(12), nullable=False)` |
| `predecessor_hash` | `Mapped[str &#124; None]` | `mapped_column(String(80), nullable=True)` |
| `terms` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `offer_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `approval_status` | `Mapped[str]` | `mapped_column(String(20), nullable=False)` |
| `expires_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint("proposer_party IN ('BUYER','SELLER') AND recipient_party IN ('BUYER','SELLER') AND proposer_party <> recipient_party", name='ck_offer_version_parties'), CheckConstraint('version >= 1', name='ck_offer_version_positive'), CheckConstraint("approval_status IN ('PENDING','APPROVED','REJECTED','REVOKED','SUPERSEDED')", name='ck_offer_version_approval_status'), UniqueConstraint('organization_id', 'case_id', 'version', name='uq_offer_case_version'), UniqueConstraint('organization_id', 'offer_hash', name='uq_offer_hash'), Index('ix_offer_case_latest', 'organization_id', 'case_id', 'version'))
```

### `bilateral_party_commands` — `BilateralPartyCommand`

Source: `python/persistence/models.py:1965`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `case_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `party` | `Mapped[str]` | `mapped_column(String(12), nullable=False)` |
| `actor_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `command_type` | `Mapped[str]` | `mapped_column(String(40), nullable=False)` |
| `expected_version` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `idempotency_key` | `Mapped[str]` | `mapped_column(String(128), nullable=False)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `payload_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `status` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint("party IN ('BUYER','SELLER','SYSTEM')", name='ck_bilateral_command_party'), CheckConstraint("status IN ('PENDING','APPLIED','REJECTED')", name='ck_bilateral_command_status'), UniqueConstraint('organization_id', 'party', 'idempotency_key', name='uq_bilateral_command_idempotency'), Index('ix_bilateral_command_case', 'organization_id', 'case_id', 'created_at'))
```

### `bilateral_party_projections` — `BilateralPartyProjection`

Source: `python/persistence/models.py:2025`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `case_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `party` | `Mapped[str]` | `mapped_column(String(12), nullable=False)` |
| `version` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `state` | `Mapped[str]` | `mapped_column(String(40), nullable=False)` |
| `released` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `source_command_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `projection_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint("party IN ('BUYER','SELLER')", name='ck_bilateral_projection_party'), UniqueConstraint('organization_id', 'case_id', 'party', 'version', name='uq_bilateral_projection_version'), UniqueConstraint('organization_id', 'projection_hash', name='uq_bilateral_projection_hash'), Index('ix_bilateral_projection_latest', 'organization_id', 'case_id', 'party', 'version'))
```

### `bilateral_release_manifests` — `BilateralReleaseManifest`

Source: `python/persistence/models.py:2058`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `case_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `owner_party` | `Mapped[str]` | `mapped_column(String(12), nullable=False)` |
| `recipient_party` | `Mapped[str]` | `mapped_column(String(12), nullable=False)` |
| `purpose` | `Mapped[str]` | `mapped_column(String(240), nullable=False)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `approved_payload_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `approval_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `status` | `Mapped[str]` | `mapped_column(String(16), nullable=False)` |
| `expires_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |
| `manifest_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint("owner_party IN ('BUYER','SELLER') AND recipient_party IN ('BUYER','SELLER') AND owner_party <> recipient_party", name='ck_release_manifest_parties'), CheckConstraint("status IN ('ACTIVE','REVOKED')", name='ck_release_manifest_status'), UniqueConstraint('organization_id', 'manifest_hash', name='uq_release_manifest_hash'), Index('ix_release_manifest_case', 'organization_id', 'case_id', 'created_at'))
```

### `bilateral_transitions` — `BilateralTransition`

Source: `python/persistence/models.py:1996`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `case_id` | `Mapped[str]` | `mapped_column(ForeignKey('bilateral_exchange_cases.id', ondelete='CASCADE'), nullable=False)` |
| `sequence` | `Mapped[int]` | `mapped_column(BigInteger, nullable=False)` |
| `command_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `command_organization_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `previous_state` | `Mapped[str]` | `mapped_column(String(40), nullable=False)` |
| `next_state` | `Mapped[str]` | `mapped_column(String(40), nullable=False)` |
| `transition_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `occurred_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'case_id', 'sequence', name='uq_bilateral_transition_sequence'), UniqueConstraint('organization_id', 'case_id', 'command_id', name='uq_bilateral_transition_command'))
```

### `calibration_runs` — `CalibrationRun`

Source: `python/persistence/models.py:894`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `purchase_request_id` | `Mapped[str]` | `mapped_column(ForeignKey('purchase_requests.id', ondelete='RESTRICT'), nullable=False)` |
| `purchase_brief_id` | `Mapped[str]` | `mapped_column(ForeignKey('purchase_brief_versions.id', ondelete='RESTRICT'), nullable=False)` |
| `result` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `proposed_purchase_brief_id` | `Mapped[str &#124; None]` | `mapped_column(ForeignKey('purchase_brief_versions.id', ondelete='RESTRICT'), nullable=True)` |
| `accepted_at` | `Mapped[datetime &#124; None]` | `mapped_column(DateTime(timezone=True), nullable=True)` |

### `candidate_feedback` — `CandidateFeedback`

Source: `python/persistence/models.py:911`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `purchase_request_id` | `Mapped[str]` | `mapped_column(ForeignKey('purchase_requests.id', ondelete='RESTRICT'), nullable=False)` |
| `candidate_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `action` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `reason` | `Mapped[str]` | `mapped_column(Text, nullable=False)` |
| `actor_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `proposed_change` | `Mapped[dict[str, Any] &#124; None]` | `mapped_column(JSON_DOCUMENT, nullable=True)` |

Constraints/indexes:

```python
(CheckConstraint("action IN ('SHORTLIST','PASS','REQUEST_OFFER','SAVE_FOR_LATER','NOT_ENOUGH_EVIDENCE')", name='ck_candidate_feedback_action'),)
```

### `candidate_set_members` — `CandidateSetMember`

Source: `python/persistence/models.py:362`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `discovery_run_id` | `Mapped[str]` | `mapped_column(ForeignKey('discovery_runs.id', ondelete='RESTRICT'), nullable=False)` |
| `canonical_identity_id` | `Mapped[str]` | `mapped_column(String(128), nullable=False)` |
| `source_record_id` | `Mapped[str]` | `mapped_column(String(128), nullable=False)` |
| `member_kind` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `disposition` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `ordinal` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `pack_id` | `Mapped[str &#124; None]` | `mapped_column(String(100), nullable=True)` |
| `pack_version` | `Mapped[int &#124; None]` | `mapped_column(Integer, nullable=True)` |
| `offer_id` | `Mapped[str &#124; None]` | `mapped_column(String(100), nullable=True)` |
| `offer_version` | `Mapped[int &#124; None]` | `mapped_column(Integer, nullable=True)` |
| `current_action_id` | `Mapped[str &#124; None]` | `mapped_column(String(100), nullable=True)` |
| `member_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'discovery_run_id', 'source_record_id', name='uq_candidate_set_source'), UniqueConstraint('organization_id', 'discovery_run_id', 'ordinal', name='uq_candidate_set_ordinal'), CheckConstraint("member_kind IN ('PACK','CURRENT_STACK','CONTRACT_ACTION','NO_ACTION')", name='ck_candidate_set_member_kind'), CheckConstraint("disposition IN ('INCLUDED','EXCLUDED','DEDUPLICATED')", name='ck_candidate_set_disposition'), CheckConstraint('ordinal >= 0', name='ck_candidate_set_ordinal_nonnegative'), CheckConstraint('pack_version IS NULL OR pack_version >= 1', name='ck_candidate_set_pack_version_positive'), CheckConstraint('offer_version IS NULL OR offer_version >= 1', name='ck_candidate_set_offer_version_positive'), Index('ix_candidate_set_members_identity', 'discovery_run_id', 'canonical_identity_id'))
```

### `cognitive_checkpoints` — `CognitiveCheckpoint`

Source: `python/persistence/models.py:1835`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `run_id` | `Mapped[str]` | `mapped_column(ForeignKey('cognitive_runs.id', ondelete='CASCADE'), nullable=False)` |
| `sequence` | `Mapped[int]` | `mapped_column(BigInteger, nullable=False)` |
| `run_version` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `projection` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `content_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'run_id', 'sequence', name='uq_cognitive_checkpoint_sequence'),)
```

### `cognitive_runs` — `CognitiveRun`

Source: `python/persistence/models.py:1758`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `principal` | `Mapped[str]` | `mapped_column(String(8), nullable=False)` |
| `actor_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `conversation_id` | `Mapped[str]` | `mapped_column(String(128), nullable=False)` |
| `turn_id` | `Mapped[str]` | `mapped_column(String(128), nullable=False)` |
| `idempotency_key` | `Mapped[str]` | `mapped_column(String(128), nullable=False)` |
| `purpose` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `input_text` | `Mapped[str]` | `mapped_column(Text, nullable=False)` |
| `input_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `manifest_hash` | `Mapped[str &#124; None]` | `mapped_column(String(80), nullable=True)` |
| `status` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `version` | `Mapped[int]` | `mapped_column(Integer, nullable=False, default=1)` |
| `budget` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `failure_code` | `Mapped[str &#124; None]` | `mapped_column(String(80), nullable=True)` |
| `cancelled_at` | `Mapped[datetime &#124; None]` | `mapped_column(DateTime(timezone=True), nullable=True)` |

Constraints/indexes:

```python
(CheckConstraint("principal IN ('SIRA','SEIL')", name='ck_cognitive_run_principal'), CheckConstraint("status IN ('CAPTURED','DECIDING','EXECUTING','WAITING','COMPLETED','FAILED','CANCELLED')", name='ck_cognitive_run_status'), UniqueConstraint('organization_id', 'actor_id', 'idempotency_key', name='uq_cognitive_run_idempotency'), UniqueConstraint('organization_id', 'conversation_id', 'turn_id', name='uq_cognitive_run_turn'), Index('ix_cognitive_run_conversation', 'organization_id', 'conversation_id', 'created_at'))
```

### `cognitive_steps` — `CognitiveStep`

Source: `python/persistence/models.py:1801`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `run_id` | `Mapped[str]` | `mapped_column(ForeignKey('cognitive_runs.id', ondelete='CASCADE'), nullable=False)` |
| `sequence` | `Mapped[int]` | `mapped_column(BigInteger, nullable=False)` |
| `kind` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `status` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `payload_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `occurred_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint("kind IN ('INPUT','DECISION','TOOL_REQUEST','TOOL_RESULT','CHECKPOINT','OUTPUT','FAILURE')", name='ck_cognitive_step_kind'), CheckConstraint("status IN ('RECORDED','AUTHORIZED','DENIED','COMPLETED','FAILED')", name='ck_cognitive_step_status'), UniqueConstraint('organization_id', 'run_id', 'sequence', name='uq_cognitive_step_sequence'))
```

### `cognitive_tool_invocations` — `CognitiveToolInvocation`

Source: `python/persistence/models.py:1859`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `run_id` | `Mapped[str]` | `mapped_column(ForeignKey('cognitive_runs.id', ondelete='CASCADE'), nullable=False)` |
| `call_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `tool_name` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `contract_version` | `Mapped[str]` | `mapped_column(String(16), nullable=False)` |
| `risk` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `arguments` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `arguments_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `status` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `output` | `Mapped[dict[str, Any] &#124; None]` | `mapped_column(JSON_DOCUMENT, nullable=True)` |
| `output_hash` | `Mapped[str &#124; None]` | `mapped_column(String(80), nullable=True)` |
| `safe_error_code` | `Mapped[str &#124; None]` | `mapped_column(String(80), nullable=True)` |

Constraints/indexes:

```python
(CheckConstraint("risk IN ('read','mutation','protected_effect')", name='ck_cognitive_tool_risk'), CheckConstraint("status IN ('REQUESTED','AUTHORIZED','RUNNING','COMPLETED','DENIED','FAILED','CANCELLED')", name='ck_cognitive_tool_status'), UniqueConstraint('organization_id', 'run_id', 'call_id', name='uq_cognitive_tool_call'))
```

### `cognitive_user_events` — `CognitiveUserEvent`

Source: `python/persistence/models.py:1892`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `run_id` | `Mapped[str]` | `mapped_column(ForeignKey('cognitive_runs.id', ondelete='CASCADE'), nullable=False)` |
| `sequence` | `Mapped[int]` | `mapped_column(BigInteger, nullable=False)` |
| `kind` | `Mapped[str]` | `mapped_column(String(40), nullable=False)` |
| `message` | `Mapped[str]` | `mapped_column(String(800), nullable=False)` |
| `retryable` | `Mapped[bool]` | `mapped_column(Boolean, nullable=False, default=False)` |
| `occurred_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint("kind IN ('message_received','work_started','clarification_needed','approval_needed','work_completed','waiting','could_not_complete')", name='ck_cognitive_user_event_kind'), UniqueConstraint('organization_id', 'run_id', 'sequence', name='uq_cognitive_user_event_sequence'))
```

### `counterfactual_records` — `CounterfactualRecordModel`

Source: `python/persistence/models.py:828`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `decision_id` | `Mapped[str &#124; None]` | `mapped_column(ForeignKey('decision_records.id', ondelete='RESTRICT'), nullable=True)` |
| `outcome` | `Mapped[str]` | `mapped_column(String(48), nullable=False)` |
| `removed_fact_ids` | `Mapped[list[str]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `alternative_fact_id_sets` | `Mapped[list[list[str]]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `tested_limit` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `base_evaluation_payload_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `alternate_evaluation_payload_hash` | `Mapped[str &#124; None]` | `mapped_column(String(80), nullable=True)` |
| `generic_evaluation_payload_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `base_selected_solution_plan_id` | `Mapped[str &#124; None]` | `mapped_column(String(64), nullable=True)` |
| `alternate_selected_solution_plan_id` | `Mapped[str &#124; None]` | `mapped_column(String(64), nullable=True)` |
| `generic_selected_solution_plan_id` | `Mapped[str &#124; None]` | `mapped_column(String(64), nullable=True)` |
| `changed_gate_ids` | `Mapped[list[str]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `record_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |

Constraints/indexes:

```python
(ForeignKeyConstraint(['organization_id', 'base_evaluation_payload_hash'], ['evaluation_runs.organization_id', 'evaluation_runs.evaluation_payload_hash'], name='fk_counterfactual_base_evaluation_hash', ondelete='RESTRICT'), ForeignKeyConstraint(['organization_id', 'alternate_evaluation_payload_hash'], ['evaluation_runs.organization_id', 'evaluation_runs.evaluation_payload_hash'], name='fk_counterfactual_alternate_evaluation_hash', ondelete='RESTRICT'), ForeignKeyConstraint(['organization_id', 'generic_evaluation_payload_hash'], ['evaluation_runs.organization_id', 'evaluation_runs.evaluation_payload_hash'], name='fk_counterfactual_generic_evaluation_hash', ondelete='RESTRICT'), UniqueConstraint('organization_id', 'record_hash', name='uq_counterfactual_record_hash'), CheckConstraint("outcome IN ('WINNER_CHANGED','NO_SMALL_COUNTERFACTUAL_FOUND')", name='ck_counterfactual_outcome'), CheckConstraint('tested_limit BETWEEN 1 AND 3', name='ck_counterfactual_tested_limit'), CheckConstraint("(outcome = 'WINNER_CHANGED' AND alternate_evaluation_payload_hash IS NOT NULL) OR (outcome = 'NO_SMALL_COUNTERFACTUAL_FOUND' AND alternate_evaluation_payload_hash IS NULL)", name='ck_counterfactual_alternate_hash'), CheckConstraint('alternate_evaluation_payload_hash IS NULL OR alternate_evaluation_payload_hash <> base_evaluation_payload_hash', name='ck_counterfactual_distinct_alternate_hash'), Index('ix_counterfactual_records_decision', 'decision_id'), Index('ix_counterfactual_records_base_hash', 'base_evaluation_payload_hash'))
```

### `decision_gate_results` — `DecisionGateResult`

Source: `python/persistence/models.py:555`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `evaluation_run_id` | `Mapped[str]` | `mapped_column(ForeignKey('evaluation_runs.id', ondelete='RESTRICT'), nullable=False)` |
| `solution_plan_record_id` | `Mapped[str]` | `mapped_column(ForeignKey('evaluation_solution_plans.id', ondelete='RESTRICT'), nullable=False)` |
| `gate_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `truth` | `Mapped[str]` | `mapped_column(String(16), nullable=False)` |
| `derived_status` | `Mapped[str &#124; None]` | `mapped_column(String(32), nullable=True)` |
| `is_primary` | `Mapped[bool]` | `mapped_column(Boolean, nullable=False, default=False)` |
| `reason_codes` | `Mapped[list[str]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `evaluated_predicates` | `Mapped[list[str]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `source_fact_ids` | `Mapped[list[str]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `permitted_resolution` | `Mapped[str &#124; None]` | `mapped_column(String(200), nullable=True)` |
| `overridable` | `Mapped[bool]` | `mapped_column(Boolean, nullable=False, default=False)` |
| `result_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'solution_plan_record_id', 'gate_id', name='uq_decision_gate_result'), CheckConstraint("truth IN ('TRUE','FALSE','UNKNOWN','CONFLICT')", name='ck_decision_gate_truth'), CheckConstraint("derived_status IS NULL OR derived_status IN ('ELIGIBLE','ELIGIBLE_WITH_EXCEPTION','CONDITIONAL','SIRA_INELIGIBLE','SEIL_PASS','UNAVAILABLE','STALE_EVIDENCE','INSUFFICIENT_EVIDENCE','CONFLICTING_EVIDENCE','AUTHORITY_REQUIRED','ADVISORY_ONLY')", name='ck_decision_gate_derived_status'), Index('ix_decision_gate_results_evaluation', 'evaluation_run_id', 'gate_id'))
```

### `decision_records` — `DecisionRecord`

Source: `python/persistence/models.py:188`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `purchase_request_id` | `Mapped[str]` | `mapped_column(ForeignKey('purchase_requests.id', ondelete='RESTRICT'), nullable=False)` |
| `purchase_brief_id` | `Mapped[str]` | `mapped_column(ForeignKey('purchase_brief_versions.id', ondelete='RESTRICT'), nullable=False)` |
| `version` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `supersedes_id` | `Mapped[str &#124; None]` | `mapped_column(ForeignKey('decision_records.id', ondelete='RESTRICT'), nullable=True)` |
| `decision_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `selected_solution_plan_id` | `Mapped[str &#124; None]` | `mapped_column(String(64), nullable=True)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'decision_hash', name='uq_decision_hash'), UniqueConstraint('organization_id', 'purchase_request_id', 'version', name='uq_decision_record_version'), CheckConstraint('version >= 1', name='ck_decision_record_version_positive'))
```

### `decision_simulations` — `DecisionSimulation`

Source: `python/persistence/models.py:218`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `decision_id` | `Mapped[str]` | `mapped_column(ForeignKey('decision_records.id', ondelete='RESTRICT'), nullable=False)` |
| `actor_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `input_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `input_payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `result_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `result_payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `authoritative` | `Mapped[bool]` | `mapped_column(Boolean, nullable=False, default=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'decision_id', 'actor_id', 'input_hash', name='uq_simulation_input'),)
```

### `decision_source_snapshots` — `DecisionSourceSnapshot`

Source: `python/persistence/models.py:145`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `purchase_request_id` | `Mapped[str]` | `mapped_column(ForeignKey('purchase_requests.id', ondelete='RESTRICT'), nullable=False)` |
| `purchase_brief_id` | `Mapped[str]` | `mapped_column(ForeignKey('purchase_brief_versions.id', ondelete='RESTRICT'), nullable=False)` |
| `stack_snapshot_id` | `Mapped[str]` | `mapped_column(ForeignKey('stack_snapshots.id', ondelete='RESTRICT'), nullable=False)` |
| `version` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `source_kind` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `content_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `accepted_by_actor_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `accepted_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint('version >= 1', name='ck_decision_source_snapshot_version'), CheckConstraint("source_kind IN ('DEVELOPMENT_FIXTURE','PROVIDER_COMPILED','MANUAL_VERIFIED')", name='ck_decision_source_snapshot_kind'), UniqueConstraint('organization_id', 'purchase_request_id', 'version', name='uq_decision_source_snapshot_version'), UniqueConstraint('organization_id', 'purchase_request_id', 'content_hash', name='uq_decision_source_snapshot_hash'))
```

### `discovery_runs` — `DiscoveryRun`

Source: `python/persistence/models.py:335`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `evaluation_run_id` | `Mapped[str]` | `mapped_column(ForeignKey('evaluation_runs.id', ondelete='RESTRICT'), nullable=False)` |
| `candidate_set_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `output_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `raw_record_count` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `canonical_product_count` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `duplicate_count` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `generated_solution_plan_count` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `excluded_count` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'evaluation_run_id', name='uq_discovery_evaluation'), CheckConstraint('raw_record_count >= 0 AND canonical_product_count >= 0 AND duplicate_count >= 0 AND generated_solution_plan_count >= 0 AND excluded_count >= 0', name='ck_discovery_counts_nonnegative'))
```

### `engagements` — `Engagement`

Source: `python/persistence/models.py:932`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `purchase_request_id` | `Mapped[str]` | `mapped_column(ForeignKey('purchase_requests.id', ondelete='RESTRICT'), nullable=False)` |
| `requirement_brief_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `requirement_brief_version` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `requirement_brief_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `candidate_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `seller_organization_id` | `Mapped[str]` | `mapped_column(ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `expected_buyer_actor_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `expected_seller_actor_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `grant_scope` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `grant_status` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `grant_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `seller_visible_requirement_brief` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `granted_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |
| `status` | `Mapped[str]` | `mapped_column(String(40), nullable=False)` |
| `buyer_consented` | `Mapped[bool]` | `mapped_column(Boolean, nullable=False, default=False)` |
| `seller_consented` | `Mapped[bool]` | `mapped_column(Boolean, nullable=False, default=False)` |
| `buyer_consent_actor_id` | `Mapped[str &#124; None]` | `mapped_column(String(100), nullable=True)` |
| `seller_consent_actor_id` | `Mapped[str &#124; None]` | `mapped_column(String(100), nullable=True)` |
| `contact_exchange` | `Mapped[dict[str, Any] &#124; None]` | `mapped_column(JSON_DOCUMENT, nullable=True)` |

Constraints/indexes:

```python
(CheckConstraint("status IN ('NOT_STARTED','SELLER_REVIEWING','SELLER_PASSED','OFFER_AVAILABLE','BUYER_CONSENT_PENDING','SELLER_CONSENT_PENDING','INTRODUCTION_READY','DECLINED','EXPIRED')", name='ck_engagement_status'), CheckConstraint('expected_buyer_actor_id <> expected_seller_actor_id', name='ck_engagement_distinct_participants'), CheckConstraint('organization_id <> seller_organization_id', name='ck_engagement_distinct_organizations'), CheckConstraint("grant_scope = 'SANITIZED_BRIEF_AND_CONTACT_CONSENT'", name='ck_engagement_grant_scope'), CheckConstraint("grant_status IN ('ACTIVE','REVOKED','EXPIRED')", name='ck_engagement_grant_status'), CheckConstraint('requirement_brief_version >= 1', name='ck_engagement_requirement_brief_version_positive'), ForeignKeyConstraint(['organization_id', 'requirement_brief_id', 'requirement_brief_version', 'requirement_brief_hash'], ['requirement_brief_versions.organization_id', 'requirement_brief_versions.id', 'requirement_brief_versions.version', 'requirement_brief_versions.content_hash'], name='fk_engagement_exact_requirement_brief', ondelete='RESTRICT'), Index('ix_engagements_requirement_brief', 'requirement_brief_id'), UniqueConstraint('organization_id', 'grant_hash', name='uq_engagement_grant_hash'))
```

### `evaluation_pipeline_versions` — `EvaluationPipelineVersion`

Source: `python/persistence/models.py:239`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `pipeline_version` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `engine_version` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `taxonomy_version` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `normalization_version` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `policy_version` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `risk_rule_set_version` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `content_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'content_hash', name='uq_evaluation_pipeline_content_hash'), Index('ix_evaluation_pipeline_version_lookup', 'organization_id', 'pipeline_version'))
```

### `evaluation_runs` — `EvaluationRun`

Source: `python/persistence/models.py:266`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `purchase_request_id` | `Mapped[str]` | `mapped_column(ForeignKey('purchase_requests.id', ondelete='RESTRICT'), nullable=False)` |
| `purchase_brief_id` | `Mapped[str]` | `mapped_column(ForeignKey('purchase_brief_versions.id', ondelete='RESTRICT'), nullable=False)` |
| `decision_id` | `Mapped[str &#124; None]` | `mapped_column(ForeignKey('decision_records.id', ondelete='RESTRICT'), nullable=True)` |
| `evaluation_pipeline_version_id` | `Mapped[str]` | `mapped_column(ForeignKey('evaluation_pipeline_versions.id', ondelete='RESTRICT'), nullable=False)` |
| `run_kind` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `evaluated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |
| `request_version` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `company_profile_version` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `stackfile_version` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `registry_version` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `candidate_set_version` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `pack_set_version` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `offer_set_version` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `quote_set_version` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `taxonomy_version` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `normalization_version` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `policy_version` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `fx_version` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `pipeline_version` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `engine_version` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `input_payload_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `input_payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `evaluation_payload_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `evaluation_payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `selected_solution_plan_id` | `Mapped[str &#124; None]` | `mapped_column(String(64), nullable=True)` |
| `rank_stability` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'evaluation_payload_hash', name='uq_evaluation_payload_hash'), UniqueConstraint('organization_id', 'purchase_request_id', 'input_payload_hash', name='uq_evaluation_run_input'), CheckConstraint("run_kind IN ('BASE','GENERIC','COUNTERFACTUAL','REPLAY')", name='ck_evaluation_run_kind'), CheckConstraint("rank_stability IN ('STABLE','UNSTABLE','UNDETERMINED')", name='ck_evaluation_rank_stability'), Index('ix_evaluation_runs_decision_id', 'decision_id'), Index('ix_evaluation_runs_request_evaluated', 'purchase_request_id', 'evaluated_at'))
```

### `evaluation_solution_plans` — `EvaluationSolutionPlan`

Source: `python/persistence/models.py:442`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `evaluation_run_id` | `Mapped[str]` | `mapped_column(ForeignKey('evaluation_runs.id', ondelete='RESTRICT'), nullable=False)` |
| `solution_plan_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `action` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `component_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `plan_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `construction_lifecycle` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `lifecycle` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `candidate_status` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `primary_reason_code` | `Mapped[str &#124; None]` | `mapped_column(String(100), nullable=True)` |
| `rank_position` | `Mapped[int &#124; None]` | `mapped_column(Integer, nullable=True)` |
| `selected` | `Mapped[bool]` | `mapped_column(Boolean, nullable=False, default=False)` |
| `ordering_frontier_member` | `Mapped[bool]` | `mapped_column(Boolean, nullable=False, default=False)` |
| `resolution_frontier_member` | `Mapped[bool]` | `mapped_column(Boolean, nullable=False, default=False)` |
| `quote_required` | `Mapped[bool]` | `mapped_column(Boolean, nullable=False, default=False)` |
| `quote_policy_reason` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `permitted_resolution` | `Mapped[str &#124; None]` | `mapped_column(String(200), nullable=True)` |
| `autonomous_execution_allowed` | `Mapped[bool]` | `mapped_column(Boolean, nullable=False, default=False)` |
| `stable_action_ids` | `Mapped[list[str]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'evaluation_run_id', 'solution_plan_id', name='uq_evaluation_solution_plan'), UniqueConstraint('organization_id', 'evaluation_run_id', 'plan_hash', name='uq_evaluation_plan_hash'), CheckConstraint("action IN ('REUSE_EXISTING','CONFIGURE_EXISTING','NO_ACTION','BUY','RENEW','RESIZE','REPLACE','CONSOLIDATE','CANCEL')", name='ck_evaluation_plan_action'), CheckConstraint("construction_lifecycle IN ('CANDIDATE','RESOLUTION_PENDING','EXECUTABLE','BLOCKED')", name='ck_evaluation_plan_construction_lifecycle'), CheckConstraint("lifecycle IN ('CANDIDATE','RESOLUTION_PENDING','EXECUTABLE','BLOCKED')", name='ck_evaluation_plan_lifecycle'), CheckConstraint("candidate_status IN ('ELIGIBLE','ELIGIBLE_WITH_EXCEPTION','CONDITIONAL','SIRA_INELIGIBLE','SEIL_PASS','UNAVAILABLE','STALE_EVIDENCE','INSUFFICIENT_EVIDENCE','CONFLICTING_EVIDENCE','AUTHORITY_REQUIRED','ADVISORY_ONLY')", name='ck_evaluation_plan_candidate_status'), CheckConstraint('rank_position IS NULL OR rank_position >= 1', name='ck_evaluation_plan_rank_positive'), Index('ix_evaluation_solution_plans_rank', 'evaluation_run_id', 'rank_position'))
```

### `evidence_assessments` — `EvidenceAssessmentRecord`

Source: `python/persistence/models.py:597`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `evaluation_run_id` | `Mapped[str]` | `mapped_column(ForeignKey('evaluation_runs.id', ondelete='RESTRICT'), nullable=False)` |
| `evidence_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `source_record_id` | `Mapped[str]` | `mapped_column(String(128), nullable=False)` |
| `field` | `Mapped[str]` | `mapped_column(String(160), nullable=False)` |
| `supported_criterion_ids` | `Mapped[list[str]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `source_allowed` | `Mapped[bool]` | `mapped_column(Boolean, nullable=False)` |
| `method_allowed` | `Mapped[bool]` | `mapped_column(Boolean, nullable=False)` |
| `scope_match` | `Mapped[bool]` | `mapped_column(Boolean, nullable=False)` |
| `reconstructable` | `Mapped[bool]` | `mapped_column(Boolean, nullable=False)` |
| `freshness_current` | `Mapped[bool &#124; None]` | `mapped_column(Boolean, nullable=True)` |
| `disputed` | `Mapped[bool]` | `mapped_column(Boolean, nullable=False)` |
| `revoked` | `Mapped[bool]` | `mapped_column(Boolean, nullable=False)` |
| `state` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `age_lower_numerator` | `Mapped[int &#124; None]` | `mapped_column(BigInteger, nullable=True)` |
| `age_lower_denominator` | `Mapped[int &#124; None]` | `mapped_column(BigInteger, nullable=True)` |
| `age_upper_numerator` | `Mapped[int &#124; None]` | `mapped_column(BigInteger, nullable=True)` |
| `age_upper_denominator` | `Mapped[int &#124; None]` | `mapped_column(BigInteger, nullable=True)` |
| `reason_codes` | `Mapped[list[str]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `assessment_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'evaluation_run_id', 'evidence_id', 'field', name='uq_evidence_assessment'), CheckConstraint("state IN ('ACCEPTABLE','UNKNOWN','STALE','CONFLICT')", name='ck_evidence_assessment_state'), CheckConstraint('age_lower_denominator IS NULL OR age_lower_denominator > 0', name='ck_evidence_age_lower_denominator_positive'), CheckConstraint('age_upper_denominator IS NULL OR age_upper_denominator > 0', name='ck_evidence_age_upper_denominator_positive'), CheckConstraint('(age_lower_numerator IS NULL AND age_lower_denominator IS NULL AND age_upper_numerator IS NULL AND age_upper_denominator IS NULL) OR (age_lower_numerator IS NOT NULL AND age_lower_denominator IS NOT NULL AND age_upper_numerator IS NOT NULL AND age_upper_denominator IS NOT NULL)', name='ck_evidence_age_bounds_complete'), Index('ix_evidence_assessments_evaluation_field', 'evaluation_run_id', 'field'))
```

### `evidence_source_versions` — `EvidenceSourceVersion`

Source: `python/persistence/qualification_models.py:37`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `product_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `object_bucket` | `Mapped[str]` | `mapped_column(String(255), nullable=False)` |
| `object_key` | `Mapped[str]` | `mapped_column(String(500), nullable=False)` |
| `object_version_id` | `Mapped[str]` | `mapped_column(String(200), nullable=False)` |
| `object_checksum` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `content_type` | `Mapped[str]` | `mapped_column(String(120), nullable=False)` |
| `size_bytes` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `parser_version` | `Mapped[str]` | `mapped_column(String(40), nullable=False)` |
| `status` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `text_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint("status IN ('PARSED','VALIDATED','PUBLISHED','REJECTED')", name='ck_evidence_source_status'), CheckConstraint('size_bytes > 0', name='ck_evidence_source_size'), UniqueConstraint('organization_id', 'product_id', 'object_checksum', name='uq_evidence_source_object'))
```

### `evidence_spans` — `EvidenceSpan`

Source: `python/persistence/qualification_models.py:66`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `source_version_id` | `Mapped[str]` | `mapped_column(ForeignKey('evidence_source_versions.id', ondelete='CASCADE'), nullable=False)` |
| `product_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `visibility` | `Mapped[str]` | `mapped_column(String(20), nullable=False)` |
| `sequence` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `start_offset` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `end_offset` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `text_content` | `Mapped[str]` | `mapped_column(Text, nullable=False)` |
| `content_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `instruction_markers` | `Mapped[list[str]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `embedding_model_id` | `Mapped[str]` | `mapped_column(String(120), nullable=False)` |
| `embedding` | `Mapped[str]` | `mapped_column(Vector1024(), nullable=False)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint("visibility IN ('PRIVATE','BUYER_SAFE','PUBLIC')", name='ck_evidence_span_visibility'), CheckConstraint('sequence >= 1', name='ck_evidence_span_sequence'), CheckConstraint('start_offset >= 0 AND end_offset > start_offset', name='ck_evidence_span_offsets'), UniqueConstraint('organization_id', 'source_version_id', 'sequence', name='uq_evidence_span_sequence'), Index('ix_evidence_span_scope', 'organization_id', 'product_id', 'visibility', 'source_version_id'))
```

### `idempotency_records` — `IdempotencyRecord`

Source: `python/persistence/models.py:1717`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `actor_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `operation` | `Mapped[str]` | `mapped_column(String(120), nullable=False)` |
| `idempotency_key` | `Mapped[str]` | `mapped_column(String(128), nullable=False)` |
| `request_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `state` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `response_status` | `Mapped[int &#124; None]` | `mapped_column(Integer, nullable=True)` |
| `response_payload` | `Mapped[dict[str, Any] &#124; None]` | `mapped_column(JSON_DOCUMENT, nullable=True)` |
| `response_reference` | `Mapped[str &#124; None]` | `mapped_column(String(128), nullable=True)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'actor_id', 'operation', 'idempotency_key', name='uq_idempotency_scope'),)
```

### `identity_merges` — `IdentityMerge`

Source: `python/persistence/models.py:416`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `discovery_run_id` | `Mapped[str]` | `mapped_column(ForeignKey('discovery_runs.id', ondelete='RESTRICT'), nullable=False)` |
| `canonical_identity_id` | `Mapped[str]` | `mapped_column(String(128), nullable=False)` |
| `merged_record_id` | `Mapped[str]` | `mapped_column(String(128), nullable=False)` |
| `reason_codes` | `Mapped[list[str]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `merge_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'discovery_run_id', 'merged_record_id', name='uq_identity_merge_record'), UniqueConstraint('organization_id', 'discovery_run_id', 'merge_hash', name='uq_identity_merge_hash'), Index('ix_identity_merges_canonical', 'discovery_run_id', 'canonical_identity_id'))
```

### `marketplace_buyer_projections` — `BuyerEngagementProjection`

Source: `python/persistence/qualification_models.py:738`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `engagement_id` | `Mapped[str]` | `mapped_column(ForeignKey('marketplace_engagements.id', ondelete='RESTRICT'), primary_key=True)` |
| `projection_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |

### `marketplace_consents` — `MarketplaceConsent`

Source: `python/persistence/qualification_models.py:795`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `engagement_id` | `Mapped[str]` | `mapped_column(ForeignKey('marketplace_engagements.id', ondelete='RESTRICT'), nullable=False)` |
| `party` | `Mapped[str]` | `mapped_column(String(12), nullable=False)` |
| `buyer_organization_id` | `Mapped[str]` | `mapped_column(ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False)` |
| `seller_organization_id` | `Mapped[str]` | `mapped_column(ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False)` |
| `actor_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `input_digest` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `approved_fields_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `state` | `Mapped[str]` | `mapped_column(String(16), nullable=False)` |
| `expires_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |
| `revoked_at` | `Mapped[datetime &#124; None]` | `mapped_column(DateTime(timezone=True), nullable=True)` |

Constraints/indexes:

```python
(CheckConstraint("party IN ('BUYER','SELLER')", name='ck_marketplace_consent_party'), CheckConstraint('buyer_organization_id <> seller_organization_id', name='ck_marketplace_consent_distinct_parties'), CheckConstraint("state IN ('GRANTED','REVOKED','EXPIRED')", name='ck_marketplace_consent_state'), UniqueConstraint('engagement_id', 'party', 'input_digest', name='uq_marketplace_consent_digest'))
```

### `marketplace_engagements` — `MarketplaceEngagement`

Source: `python/persistence/qualification_models.py:706`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `mission_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `decision_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `buyer_organization_id` | `Mapped[str]` | `mapped_column(ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False)` |
| `seller_organization_id` | `Mapped[str]` | `mapped_column(ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False)` |
| `product_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `input_digest` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `buyer_safe_requirement` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `buyer_safe_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `state` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `expires_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint("state IN ('OPEN','RESPONDED','CONSENT_PENDING','INTRODUCED','EXPIRED','INVALIDATED')", name='ck_marketplace_engagement_state'), CheckConstraint('buyer_organization_id <> seller_organization_id', name='ck_marketplace_distinct_parties'), UniqueConstraint('decision_id', 'seller_organization_id', name='uq_marketplace_engagement'))
```

### `marketplace_seller_projections` — `SellerEngagementProjection`

Source: `python/persistence/qualification_models.py:748`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `engagement_id` | `Mapped[str]` | `mapped_column(ForeignKey('marketplace_engagements.id', ondelete='RESTRICT'), primary_key=True)` |
| `projection_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |

### `marketplace_seller_responses` — `SellerResponse`

Source: `python/persistence/qualification_models.py:758`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `engagement_id` | `Mapped[str]` | `mapped_column(ForeignKey('marketplace_engagements.id', ondelete='RESTRICT'), nullable=False)` |
| `buyer_organization_id` | `Mapped[str]` | `mapped_column(ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False)` |
| `seller_organization_id` | `Mapped[str]` | `mapped_column(ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False)` |
| `input_digest` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `response` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `cited_evidence_ids` | `Mapped[list[Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `message` | `Mapped[str &#124; None]` | `mapped_column(Text, nullable=True)` |
| `actor_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint('buyer_organization_id <> seller_organization_id', name='ck_marketplace_response_distinct_parties'), CheckConstraint('organization_id = seller_organization_id', name='ck_marketplace_response_seller_owned'), CheckConstraint("response IN ('FIT','ANTI_FIT','NEEDS_INFO')", name='ck_marketplace_seller_response'), UniqueConstraint('organization_id', 'engagement_id', 'input_digest', name='uq_marketplace_response'))
```

### `organizations` — `Organization`

Source: `python/persistence/models.py:64`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `name` | `Mapped[str]` | `mapped_column(String(200), nullable=False)` |
| `version` | `Mapped[int]` | `mapped_column(Integer, nullable=False, default=1)` |

### `outbox_events` — `OutboxEvent`

Source: `python/persistence/models.py:1741`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `aggregate_type` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `aggregate_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `event_type` | `Mapped[str]` | `mapped_column(String(120), nullable=False)` |
| `event_key` | `Mapped[str]` | `mapped_column(String(255), nullable=False)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `occurred_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `published_at` | `Mapped[datetime &#124; None]` | `mapped_column(DateTime(timezone=True), nullable=True)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'event_key', name='uq_outbox_event_key'),)
```

### `outcome_checkpoints` — `OutcomeCheckpoint`

Source: `python/persistence/models.py:1065`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `purchase_intent_id` | `Mapped[str]` | `mapped_column(ForeignKey('purchase_intents.id', ondelete='RESTRICT'), nullable=False)` |
| `decision_id` | `Mapped[str]` | `mapped_column(ForeignKey('decision_records.id', ondelete='RESTRICT'), nullable=False)` |
| `decision_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `solution_plan_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `metric_id` | `Mapped[str]` | `mapped_column(String(128), nullable=False)` |
| `target_value` | `Mapped[Decimal]` | `mapped_column(Numeric(30, 6), nullable=False)` |
| `target_operator` | `Mapped[str]` | `mapped_column(String(8), nullable=False)` |
| `observed_value` | `Mapped[Decimal]` | `mapped_column(Numeric(30, 6), nullable=False)` |
| `checkpoint_days` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `measurement_started_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |
| `checkpoint_due_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |
| `observed_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |
| `state` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `source_class` | `Mapped[str]` | `mapped_column(String(40), nullable=False)` |
| `source_reference_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `recorded_by_actor_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `checkpoint_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `preference_proposal` | `Mapped[dict[str, Any] &#124; None]` | `mapped_column(JSON_DOCUMENT, nullable=True)` |

Constraints/indexes:

```python
(CheckConstraint('checkpoint_days BETWEEN 1 AND 365', name='ck_outcome_checkpoint_days'), CheckConstraint("target_operator IN ('gte','lte')", name='ck_outcome_target_operator'), CheckConstraint("state IN ('MEASURING','ACHIEVED','NOT_ACHIEVED','INCONCLUSIVE')", name='ck_outcome_state'), CheckConstraint("source_class IN ('SYSTEM_OBSERVATION','HUMAN_ATTESTATION','PROVIDER_REPORT')", name='ck_outcome_source_class'), UniqueConstraint('organization_id', 'checkpoint_hash', name='uq_outcome_checkpoint_hash'), Index('ix_outcome_intent_metric', 'organization_id', 'purchase_intent_id', 'metric_id', 'observed_at'))
```

### `payment_handoffs` — `PaymentHandoff`

Source: `python/persistence/models.py:1278`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `purchase_intent_id` | `Mapped[str]` | `mapped_column(ForeignKey('purchase_intents.id', ondelete='RESTRICT'), nullable=False)` |
| `approval_request_id` | `Mapped[str]` | `mapped_column(ForeignKey('approval_requests.id', ondelete='RESTRICT'), nullable=False)` |
| `intent_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `handoff_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `destination_url` | `Mapped[str]` | `mapped_column(Text, nullable=False)` |
| `recipient` | `Mapped[str]` | `mapped_column(String(200), nullable=False)` |
| `amount` | `Mapped[Decimal]` | `mapped_column(Numeric(20, 2), nullable=False)` |
| `currency` | `Mapped[str]` | `mapped_column(String(3), nullable=False)` |
| `reference` | `Mapped[str]` | `mapped_column(String(160), nullable=False)` |
| `status` | `Mapped[str]` | `mapped_column(String(24), nullable=False, default='READY')` |
| `expires_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |
| `opened_at` | `Mapped[datetime &#124; None]` | `mapped_column(DateTime(timezone=True), nullable=True)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'handoff_hash', name='uq_payment_handoff_hash'), UniqueConstraint('organization_id', 'purchase_intent_id', 'approval_request_id', name='uq_payment_handoff_approval'), CheckConstraint('amount >= 0', name='ck_payment_handoff_amount_nonnegative'), CheckConstraint('currency = upper(currency)', name='ck_payment_handoff_currency_upper'), CheckConstraint("status IN ('READY','OPENED','EXPIRED','CANCELLED')", name='ck_payment_handoff_status'), CheckConstraint("(status = 'OPENED' AND opened_at IS NOT NULL) OR (status <> 'OPENED' AND opened_at IS NULL)", name='ck_payment_handoff_opened_state'), Index('ix_payment_handoff_intent_status', 'organization_id', 'purchase_intent_id', 'status'))
```

### `purchase_brief_versions` — `PurchaseBriefVersion`

Source: `python/persistence/models.py:92`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `purchase_request_id` | `Mapped[str]` | `mapped_column(ForeignKey('purchase_requests.id', ondelete='RESTRICT'), nullable=False)` |
| `version` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `status` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `content_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `supersedes_id` | `Mapped[str &#124; None]` | `mapped_column(ForeignKey('purchase_brief_versions.id', ondelete='RESTRICT'), nullable=True)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'purchase_request_id', 'version', name='uq_purchase_brief_version'),)
```

### `purchase_intents` — `PurchaseIntent`

Source: `python/persistence/models.py:1009`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `decision_id` | `Mapped[str]` | `mapped_column(ForeignKey('decision_records.id', ondelete='RESTRICT'), nullable=False)` |
| `decision_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `solution_plan_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `stack_patch_id` | `Mapped[str]` | `mapped_column(ForeignKey('stack_patches.id', ondelete='RESTRICT'), nullable=False)` |
| `intent_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `merchant_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `merchant_name` | `Mapped[str]` | `mapped_column(String(200), nullable=False)` |
| `merchant_url` | `Mapped[str]` | `mapped_column(Text, nullable=False)` |
| `approved_merchant_chain_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `pack_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `pack_version` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `offer_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `offer_version` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `quote_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `quote_version` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `quote_expires_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |
| `amount` | `Mapped[Decimal]` | `mapped_column(Numeric(20, 2), nullable=False)` |
| `currency` | `Mapped[str]` | `mapped_column(String(3), nullable=False)` |
| `expected_fulfillments` | `Mapped[list[dict[str, Any]]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `approval_status` | `Mapped[str]` | `mapped_column(String(32), nullable=False, default='NOT_REQUESTED')` |
| `version` | `Mapped[int]` | `mapped_column(Integer, nullable=False, default=1)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'intent_hash', name='uq_purchase_intent_hash'), UniqueConstraint('organization_id', 'decision_id', 'solution_plan_id', 'quote_id', 'quote_version', name='uq_purchase_intent_business_lock'), CheckConstraint('quote_version >= 1', name='ck_purchase_intent_quote_version_positive'), CheckConstraint('amount >= 0', name='ck_purchase_intent_amount_nonnegative'), CheckConstraint('currency = upper(currency)', name='ck_purchase_intent_currency_upper'), CheckConstraint("approval_status IN ('NOT_REQUESTED','PENDING','APPROVED','REJECTED','REVOKED','EXPIRED','SUPERSEDED')", name='ck_purchase_intent_approval_status'))
```

### `purchase_requests` — `PurchaseRequest`

Source: `python/persistence/models.py:72`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `intent` | `Mapped[str]` | `mapped_column(Text, nullable=False)` |
| `status` | `Mapped[str]` | `mapped_column(String(40), nullable=False)` |
| `visibility` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `version` | `Mapped[int]` | `mapped_column(Integer, nullable=False, default=1)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `request_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint("visibility IN ('PRIVATE','SELECTIVE','OPEN_RFP')", name='ck_purchase_request_visibility'), UniqueConstraint('organization_id', 'request_hash', name='uq_purchase_request_hash'))
```

### `qualification_active_product_bundles` — `ActiveProductBundle`

Source: `python/persistence/qualification_models.py:413`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `product_id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `bundle_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `bundle_digest` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `generation` | `Mapped[int]` | `mapped_column(Integer, nullable=False, default=1)` |

Constraints/indexes:

```python
(CheckConstraint('generation >= 1', name='ck_qualification_active_bundle_generation'), ForeignKeyConstraint(['organization_id', 'bundle_id', 'bundle_digest'], ['qualification_product_bundles.organization_id', 'qualification_product_bundles.id', 'qualification_product_bundles.digest'], ondelete='RESTRICT'))
```

### `qualification_attempt_checkpoints` — `AttemptCheckpoint`

Source: `python/persistence/qualification_models.py:606`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `attempt_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `generation` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `sequence` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `kind` | `Mapped[str]` | `mapped_column(String(48), nullable=False)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `occurred_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint('sequence >= 1', name='ck_qualification_checkpoint_sequence'), UniqueConstraint('organization_id', 'attempt_id', 'sequence', name='uq_qualification_checkpoint_sequence'), ForeignKeyConstraint(['organization_id', 'attempt_id', 'generation'], ['qualification_attempts.organization_id', 'qualification_attempts.id', 'qualification_attempts.generation'], ondelete='RESTRICT'))
```

### `qualification_attempt_dependencies` — `AttemptDependency`

Source: `python/persistence/qualification_models.py:579`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `attempt_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `dependency_kind` | `Mapped[str]` | `mapped_column(String(40), nullable=False)` |
| `dependency_organization_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `dependency_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `dependency_version` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `dependency_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'attempt_id', 'dependency_kind', 'dependency_id', name='uq_qualification_attempt_dependency'), ForeignKeyConstraint(['organization_id', 'attempt_id'], ['qualification_attempts.organization_id', 'qualification_attempts.id'], ondelete='RESTRICT'))
```

### `qualification_attempts` — `QualificationAttempt`

Source: `python/persistence/qualification_models.py:531`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `mission_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `root_attempt_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `predecessor_attempt_id` | `Mapped[str &#124; None]` | `mapped_column(String(64), nullable=True)` |
| `replacement_depth` | `Mapped[int]` | `mapped_column(Integer, nullable=False, default=0)` |
| `state` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `generation` | `Mapped[int]` | `mapped_column(Integer, nullable=False, default=0)` |
| `lease_owner` | `Mapped[str &#124; None]` | `mapped_column(String(100), nullable=True)` |
| `lease_expires_at` | `Mapped[datetime &#124; None]` | `mapped_column(DateTime(timezone=True), nullable=True)` |
| `input_digest` | `Mapped[str &#124; None]` | `mapped_column(String(80), nullable=True)` |
| `stale_reason` | `Mapped[str &#124; None]` | `mapped_column(String(160), nullable=True)` |

Constraints/indexes:

```python
(CheckConstraint('replacement_depth BETWEEN 0 AND 3', name='ck_qualification_replacement_depth'), CheckConstraint('generation >= 0', name='ck_qualification_attempt_generation'), CheckConstraint("state IN ('QUEUED','RUNNING','SNAPSHOT_COMPLETE','STALE','COMPLETED','FAILED','CANCELLED')", name='ck_qualification_attempt_state'), UniqueConstraint('organization_id', 'predecessor_attempt_id', name='uq_qualification_direct_successor'), UniqueConstraint('organization_id', 'id', 'generation', name='uq_qualification_attempt_fence'), UniqueConstraint('organization_id', 'id', name='uq_qualification_attempt_tenant_id'), ForeignKeyConstraint(['organization_id', 'mission_id'], ['qualification_missions.organization_id', 'qualification_missions.id'], ondelete='RESTRICT'), Index('ix_qualification_attempt_claim', 'organization_id', 'state', 'lease_expires_at'))
```

### `qualification_catalog_projection_versions` — `CatalogProjectionVersion`

Source: `python/persistence/qualification_models.py:284`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `product_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `version` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `content_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `buyer_safe_payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint('version >= 1', name='ck_qualification_catalog_version'), UniqueConstraint('organization_id', 'product_id', 'version', name='uq_qualification_catalog_version'), UniqueConstraint('organization_id', 'id', 'content_hash', name='uq_qualification_catalog_binding'), UniqueConstraint('organization_id', 'id', name='uq_qualification_catalog_tenant_id'))
```

### `qualification_company_context_embeddings` — `CompanyContextEmbedding`

Source: `python/persistence/qualification_models.py:223`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `item_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `version_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `kind` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `content_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `model_id` | `Mapped[str]` | `mapped_column(String(160), nullable=False)` |
| `dimensions` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `embedding` | `Mapped[str]` | `mapped_column(Vector1024(), nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint('dimensions = 1024', name='ck_qualification_context_embedding_dimensions'), UniqueConstraint('organization_id', 'version_id', 'content_hash', name='uq_qualification_context_embedding'), ForeignKeyConstraint(['organization_id', 'version_id', 'content_hash'], ['qualification_company_context_versions.organization_id', 'qualification_company_context_versions.id', 'qualification_company_context_versions.content_hash'], ondelete='RESTRICT'), Index('ix_qualification_context_embedding_scope', 'organization_id', 'kind', 'version_id'))
```

### `qualification_company_context_items` — `CompanyContextItem`

Source: `python/persistence/qualification_models.py:110`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `kind` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `label` | `Mapped[str]` | `mapped_column(String(160), nullable=False)` |
| `state` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `current_version_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `current_version` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `current_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint("kind IN ('REQUIREMENT','CONSTRAINT','STACK','POLICY','PREFERENCE','NOTE')", name='ck_qualification_context_kind'), CheckConstraint("state IN ('ACTIVE','RETIRED')", name='ck_qualification_context_state'), CheckConstraint('current_version >= 1', name='ck_qualification_context_version'), UniqueConstraint('organization_id', 'id', name='uq_qualification_context_item_tenant_id'), UniqueConstraint('organization_id', 'id', 'current_version_id', 'current_hash', name='uq_qualification_context_current_binding'))
```

### `qualification_company_context_versions` — `CompanyContextVersion`

Source: `python/persistence/qualification_models.py:139`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `item_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `version` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `content_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `changed_by_actor_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `change_reason` | `Mapped[str]` | `mapped_column(String(500), nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint('version >= 1', name='ck_qualification_context_revision'), UniqueConstraint('organization_id', 'item_id', 'version', name='uq_qualification_context_revision'), UniqueConstraint('organization_id', 'id', 'content_hash', name='uq_qualification_context_binding'), ForeignKeyConstraint(['organization_id', 'item_id'], ['qualification_company_context_items.organization_id', 'qualification_company_context_items.id'], ondelete='RESTRICT'))
```

### `qualification_consumer_receipts` — `ConsumerReceipt`

Source: `python/persistence/qualification_models.py:857`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `consumer_name` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `message_id` | `Mapped[str]` | `mapped_column(String(160), nullable=False)` |
| `payload_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `result_ref` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `processed_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'consumer_name', 'message_id', name='uq_qualification_consumer_receipt'),)
```

### `qualification_decision_dependencies` — `DecisionDependency`

Source: `python/persistence/qualification_models.py:678`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `decision_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `dependency_kind` | `Mapped[str]` | `mapped_column(String(40), nullable=False)` |
| `dependency_organization_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `dependency_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `dependency_version` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `dependency_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `cited` | `Mapped[bool]` | `mapped_column(Boolean, nullable=False, default=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'decision_id', 'dependency_kind', 'dependency_id', name='uq_qualification_decision_dependency'), ForeignKeyConstraint(['organization_id', 'decision_id'], ['qualification_decisions.organization_id', 'qualification_decisions.id'], ondelete='RESTRICT'))
```

### `qualification_decisions` — `QualificationDecision`

Source: `python/persistence/qualification_models.py:636`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `mission_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `attempt_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `input_digest` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `decision_digest` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `recommended_product_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `approval_state` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `current` | `Mapped[bool]` | `mapped_column(Boolean, nullable=False, default=True)` |

Constraints/indexes:

```python
(CheckConstraint("approval_state IN ('PENDING','APPROVED','REJECTED','INVALIDATED')", name='ck_qualification_decision_approval'), UniqueConstraint('organization_id', 'attempt_id', name='uq_qualification_decision_attempt'), UniqueConstraint('organization_id', 'mission_id', 'input_digest', name='uq_qualification_decision_input'), UniqueConstraint('organization_id', 'id', name='uq_qualification_decision_tenant_id'), ForeignKeyConstraint(['organization_id', 'attempt_id'], ['qualification_attempts.organization_id', 'qualification_attempts.id'], ondelete='RESTRICT'), Index('uq_qualification_current_decision', 'organization_id', 'mission_id', unique=True, cockroachdb_where=text('current'), postgresql_where=text('current')))
```

### `qualification_effects` — `QualificationEffect`

Source: `python/persistence/qualification_models.py:879`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `effect_kind` | `Mapped[str]` | `mapped_column(String(48), nullable=False)` |
| `semantic_key` | `Mapped[str]` | `mapped_column(String(200), nullable=False)` |
| `state` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `result_ref` | `Mapped[str &#124; None]` | `mapped_column(String(100), nullable=True)` |

Constraints/indexes:

```python
(CheckConstraint("state IN ('RESERVED','DELIVERED','FAILED','CANCELLED')", name='ck_qualification_effect_state'), UniqueConstraint('organization_id', 'effect_kind', 'semantic_key', name='uq_qualification_effect'))
```

### `qualification_evidence_versions` — `EvidenceVersion`

Source: `python/persistence/qualification_models.py:308`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `product_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `version` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `content_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `source_object_key` | `Mapped[str]` | `mapped_column(String(500), nullable=False)` |
| `source_checksum` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `facts` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `eligible` | `Mapped[bool]` | `mapped_column(Boolean, nullable=False, default=False)` |
| `reviewed_by_actor_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint('version >= 1', name='ck_qualification_evidence_version'), UniqueConstraint('organization_id', 'product_id', 'version', name='uq_qualification_evidence_version'), UniqueConstraint('organization_id', 'id', 'content_hash', name='uq_qualification_evidence_binding'))
```

### `qualification_mission_bundles` — `QualificationMissionBundle`

Source: `python/persistence/qualification_models.py:500`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `mission_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `attempt_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `product_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `seller_organization_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `bundle_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `bundle_digest` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'attempt_id', 'product_id', name='uq_qualification_attempt_product'), ForeignKeyConstraint(['organization_id', 'mission_id'], ['qualification_missions.organization_id', 'qualification_missions.id'], ondelete='RESTRICT'), ForeignKeyConstraint(['organization_id', 'attempt_id'], ['qualification_attempts.organization_id', 'qualification_attempts.id'], ondelete='RESTRICT'))
```

### `qualification_missions` — `QualificationMission`

Source: `python/persistence/qualification_models.py:471`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `buyer_context_version_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `buyer_context_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `buyer_context_payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `requirement_brief_version_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `requirement_brief_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `requirement_brief_payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `procurement_policy_version` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `procurement_policy_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `procurement_policy_payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `trace_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `state` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `version` | `Mapped[int]` | `mapped_column(Integer, nullable=False, default=1)` |

Constraints/indexes:

```python
(CheckConstraint("state IN ('DRAFT','READY','RUNNING','AWAITING_APPROVAL','COMPLETED','FAILED','CANCELLED')", name='ck_qualification_mission_state'), UniqueConstraint('organization_id', 'id', name='uq_qualification_mission_tenant_id'))
```

### `qualification_product_bundle_members` — `ProductBundleMember`

Source: `python/persistence/qualification_models.py:379`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `bundle_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `ordinal` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `member_kind` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `member_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `member_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint('ordinal >= 0', name='ck_qualification_bundle_member_ordinal'), CheckConstraint("member_kind IN ('PRODUCT_TWIN','CATALOG_PROJECTION','EVIDENCE')", name='ck_qualification_bundle_member_kind'), UniqueConstraint('organization_id', 'bundle_id', 'ordinal', name='uq_qualification_bundle_ordinal'), UniqueConstraint('organization_id', 'bundle_id', 'member_kind', 'member_id', name='uq_qualification_bundle_member'), ForeignKeyConstraint(['organization_id', 'bundle_id'], ['qualification_product_bundles.organization_id', 'qualification_product_bundles.id'], ondelete='RESTRICT'))
```

### `qualification_product_bundles` — `ProductBundle`

Source: `python/persistence/qualification_models.py:335`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `product_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `version` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `product_twin_version_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `catalog_projection_version_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `disclosure_policy_version` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `embedding_profile` | `Mapped[str]` | `mapped_column(String(120), nullable=False)` |
| `digest` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `state` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `activated_at` | `Mapped[datetime &#124; None]` | `mapped_column(DateTime(timezone=True), nullable=True)` |

Constraints/indexes:

```python
(CheckConstraint('version >= 1', name='ck_qualification_bundle_version'), CheckConstraint("state IN ('CANDIDATE','READY','ACTIVE','SUPERSEDED','RETRACTED')", name='ck_qualification_bundle_state'), UniqueConstraint('organization_id', 'product_id', 'version', name='uq_qualification_bundle_version'), UniqueConstraint('organization_id', 'id', 'digest', name='uq_qualification_bundle_binding'), UniqueConstraint('organization_id', 'id', name='uq_qualification_bundle_tenant_id'), ForeignKeyConstraint(['organization_id', 'product_twin_version_id'], ['qualification_product_twin_versions.organization_id', 'qualification_product_twin_versions.id'], ondelete='RESTRICT'), ForeignKeyConstraint(['organization_id', 'catalog_projection_version_id'], ['qualification_catalog_projection_versions.organization_id', 'qualification_catalog_projection_versions.id'], ondelete='RESTRICT'))
```

### `qualification_product_embeddings` — `ProductEmbedding`

Source: `python/persistence/qualification_models.py:435`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `bundle_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `product_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `category` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `visibility` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `content_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `model_id` | `Mapped[str]` | `mapped_column(String(160), nullable=False)` |
| `dimensions` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `embedding` | `Mapped[str]` | `mapped_column(Vector1024(), nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint('dimensions = 1024', name='ck_qualification_embedding_dimensions'), CheckConstraint("visibility IN ('BUYER_SAFE','PUBLIC')", name='ck_qualification_embedding_visibility'), UniqueConstraint('organization_id', 'bundle_id', 'content_hash', name='uq_qualification_embedding'), ForeignKeyConstraint(['organization_id', 'bundle_id'], ['qualification_product_bundles.organization_id', 'qualification_product_bundles.id'], ondelete='RESTRICT'), Index('ix_qualification_embedding_scope', 'organization_id', 'category', 'visibility', 'bundle_id'))
```

### `qualification_product_twin_versions` — `ProductTwinVersion`

Source: `python/persistence/qualification_models.py:261`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `product_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `version` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `content_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `published_by_actor_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `published_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint('version >= 1', name='ck_qualification_twin_version'), UniqueConstraint('organization_id', 'product_id', 'version', name='uq_qualification_twin_version'), UniqueConstraint('organization_id', 'id', 'content_hash', name='uq_qualification_twin_binding'), UniqueConstraint('organization_id', 'id', name='uq_qualification_twin_tenant_id'))
```

### `qualification_workspace_setting_versions` — `WorkspaceSettingsVersion`

Source: `python/persistence/qualification_models.py:188`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `settings_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `version` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `content_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `changed_by_actor_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `change_reason` | `Mapped[str]` | `mapped_column(String(500), nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint('version >= 1', name='ck_workspace_settings_revision'), ForeignKeyConstraint(['organization_id', 'settings_id'], ['qualification_workspace_settings.organization_id', 'qualification_workspace_settings.id'], ondelete='RESTRICT'), UniqueConstraint('organization_id', 'settings_id', 'version', name='uq_workspace_settings_revision'), UniqueConstraint('organization_id', 'id', 'content_hash', name='uq_workspace_settings_binding'))
```

### `qualification_workspace_settings` — `WorkspaceSettings`

Source: `python/persistence/qualification_models.py:169`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `party` | `Mapped[str]` | `mapped_column(String(12), nullable=False)` |
| `current_version_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `current_version` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `current_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint("party IN ('BUYER','SELLER')", name='ck_workspace_settings_party'), CheckConstraint('current_version >= 1', name='ck_workspace_settings_version'), UniqueConstraint('organization_id', 'party', name='uq_workspace_settings_party'), UniqueConstraint('organization_id', 'id', name='uq_workspace_settings_tenant_id'))
```

### `qualified_introductions` — `QualifiedIntroduction`

Source: `python/persistence/qualification_models.py:831`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `engagement_id` | `Mapped[str]` | `mapped_column(ForeignKey('marketplace_engagements.id', ondelete='RESTRICT'), nullable=False)` |
| `decision_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `buyer_organization_id` | `Mapped[str]` | `mapped_column(ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False)` |
| `seller_organization_id` | `Mapped[str]` | `mapped_column(ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False)` |
| `input_digest` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `shared_fields_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `receipt_payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('engagement_id', name='uq_qualified_introduction_engagement'), UniqueConstraint('decision_id', 'seller_organization_id', name='uq_qualified_introduction_effect'))
```

### `requirement_brief_versions` — `RequirementBriefVersion`

Source: `python/persistence/models.py:114`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `purchase_request_id` | `Mapped[str]` | `mapped_column(ForeignKey('purchase_requests.id', ondelete='RESTRICT'), nullable=False)` |
| `purchase_brief_id` | `Mapped[str]` | `mapped_column(ForeignKey('purchase_brief_versions.id', ondelete='RESTRICT'), nullable=False)` |
| `version` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `content_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'purchase_request_id', 'version', name='uq_requirement_brief_version'), UniqueConstraint('organization_id', 'id', 'version', 'content_hash', name='uq_requirement_brief_exact_binding'))
```

### `result_artifacts` — `ResultArtifact`

Source: `python/persistence/models.py:1181`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `action_run_id` | `Mapped[str]` | `mapped_column(ForeignKey('action_runs.id', ondelete='RESTRICT'), nullable=False)` |
| `artifact_type` | `Mapped[str]` | `mapped_column(String(40), nullable=False)` |
| `verification_state` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `actor_id` | `Mapped[str &#124; None]` | `mapped_column(String(100), nullable=True)` |
| `owner_role` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `occurred_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |
| `verified_at` | `Mapped[datetime &#124; None]` | `mapped_column(DateTime(timezone=True), nullable=True)` |
| `safe_label` | `Mapped[str]` | `mapped_column(String(200), nullable=False)` |
| `href` | `Mapped[str]` | `mapped_column(Text, nullable=False)` |
| `stack_patch_id` | `Mapped[str &#124; None]` | `mapped_column(ForeignKey('stack_patches.id', ondelete='RESTRICT'), nullable=True)` |
| `artifact_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'action_run_id', 'artifact_hash', name='uq_result_artifact_hash'), CheckConstraint("artifact_type IN ('DECISION_RECORD','CONFIGURATION_CHANGE','CONTRACT_CONFIRMATION','CANCELLATION_CONFIRMATION','MIGRATION_RECORD','STACK_PATCH','OUTCOME_CHECKPOINT')", name='ck_result_artifact_type'), CheckConstraint("verification_state IN ('PENDING','VERIFIED','FAILED','REVOKED')", name='ck_result_artifact_verification_state'), CheckConstraint('verified_at IS NULL OR verified_at >= occurred_at', name='ck_result_artifact_verification_order'), CheckConstraint("verification_state <> 'VERIFIED' OR verified_at IS NOT NULL", name='ck_result_artifact_verified_timestamp'), Index('ix_result_artifacts_action_type', 'action_run_id', 'artifact_type'))
```

### `robustness_frontiers` — `RobustnessFrontier`

Source: `python/persistence/models.py:791`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `evaluation_run_id` | `Mapped[str]` | `mapped_column(ForeignKey('evaluation_runs.id', ondelete='RESTRICT'), nullable=False)` |
| `solution_plan_record_id` | `Mapped[str]` | `mapped_column(ForeignKey('evaluation_solution_plans.id', ondelete='RESTRICT'), nullable=False)` |
| `frontier_kind` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `decision_rank_stability` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `member` | `Mapped[bool]` | `mapped_column(Boolean, nullable=False)` |
| `can_beat_selected` | `Mapped[bool &#124; None]` | `mapped_column(Boolean, nullable=True)` |
| `permitted_resolution` | `Mapped[str &#124; None]` | `mapped_column(String(200), nullable=True)` |
| `frontier_payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `frontier_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'solution_plan_record_id', 'frontier_kind', name='uq_robustness_frontier_kind'), CheckConstraint("frontier_kind IN ('ORDERING','RESOLUTION','BOUND_UNAVAILABLE')", name='ck_robustness_frontier_kind'), CheckConstraint("decision_rank_stability IN ('STABLE','UNSTABLE','UNDETERMINED')", name='ck_robustness_rank_stability'), Index('ix_robustness_frontiers_evaluation', 'evaluation_run_id', 'frontier_kind'))
```

### `runtime_ticket_uses` — `RuntimeTicketUse`

Source: `python/persistence/models.py:1921`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `ticket_id` | `Mapped[str]` | `mapped_column(String(128), nullable=False)` |
| `nonce_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `expires_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |
| `consumed_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'ticket_id', 'nonce_hash', name='uq_runtime_ticket_use'), Index('ix_runtime_ticket_expiry', 'organization_id', 'expires_at'))
```

### `score_bounds` — `ScoreBound`

Source: `python/persistence/models.py:714`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `evaluation_run_id` | `Mapped[str]` | `mapped_column(ForeignKey('evaluation_runs.id', ondelete='RESTRICT'), nullable=False)` |
| `solution_plan_record_id` | `Mapped[str]` | `mapped_column(ForeignKey('evaluation_solution_plans.id', ondelete='RESTRICT'), nullable=False)` |
| `dimension` | `Mapped[str]` | `mapped_column(String(48), nullable=False)` |
| `bound_status` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `value_kind` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `lower_numerator` | `Mapped[int &#124; None]` | `mapped_column(BigInteger, nullable=True)` |
| `lower_denominator` | `Mapped[int &#124; None]` | `mapped_column(BigInteger, nullable=True)` |
| `base_numerator` | `Mapped[int &#124; None]` | `mapped_column(BigInteger, nullable=True)` |
| `base_denominator` | `Mapped[int &#124; None]` | `mapped_column(BigInteger, nullable=True)` |
| `upper_numerator` | `Mapped[int &#124; None]` | `mapped_column(BigInteger, nullable=True)` |
| `upper_denominator` | `Mapped[int &#124; None]` | `mapped_column(BigInteger, nullable=True)` |
| `currency` | `Mapped[str &#124; None]` | `mapped_column(String(3), nullable=True)` |
| `unavailable_reason` | `Mapped[str &#124; None]` | `mapped_column(String(160), nullable=True)` |
| `calculation_payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `bound_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'solution_plan_record_id', 'dimension', name='uq_score_bound_dimension'), CheckConstraint("dimension IN ('PREFERENCE','STACK_RISK','TCO','DECISION_MATERIAL_COVERAGE','EVIDENCE_AGE','HARD_COVERAGE','UNIVERSE_COVERAGE')", name='ck_score_bound_dimension'), CheckConstraint("bound_status IN ('AVAILABLE','BOUND_UNAVAILABLE')", name='ck_score_bound_status'), CheckConstraint("value_kind IN ('RATIO','RISK_ORDINAL','MONEY','COUNT')", name='ck_score_bound_value_kind'), CheckConstraint("(bound_status = 'AVAILABLE' AND lower_numerator IS NOT NULL AND lower_denominator IS NOT NULL AND base_numerator IS NOT NULL AND base_denominator IS NOT NULL AND upper_numerator IS NOT NULL AND upper_denominator IS NOT NULL AND unavailable_reason IS NULL) OR (bound_status = 'BOUND_UNAVAILABLE' AND unavailable_reason IS NOT NULL)", name='ck_score_bound_availability'), CheckConstraint('(lower_denominator IS NULL OR lower_denominator > 0) AND (base_denominator IS NULL OR base_denominator > 0) AND (upper_denominator IS NULL OR upper_denominator > 0)', name='ck_score_bound_denominators_positive'), CheckConstraint('currency IS NULL OR currency = upper(currency)', name='ck_score_bound_currency_upper'), CheckConstraint("(value_kind = 'MONEY' AND currency IS NOT NULL) OR (value_kind <> 'MONEY' AND currency IS NULL)", name='ck_score_bound_currency_kind'), CheckConstraint("value_kind <> 'RISK_ORDINAL' OR bound_status = 'BOUND_UNAVAILABLE' OR (lower_denominator = 1 AND base_denominator = 1 AND upper_denominator = 1 AND lower_numerator BETWEEN 0 AND 3 AND base_numerator BETWEEN 0 AND 3 AND upper_numerator BETWEEN 0 AND 3)", name='ck_score_bound_risk_ordinal'), Index('ix_score_bounds_evaluation_dimension', 'evaluation_run_id', 'dimension'))
```

### `score_components` — `ScoreComponentRecord`

Source: `python/persistence/models.py:654`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `evaluation_run_id` | `Mapped[str]` | `mapped_column(ForeignKey('evaluation_runs.id', ondelete='RESTRICT'), nullable=False)` |
| `solution_plan_record_id` | `Mapped[str]` | `mapped_column(ForeignKey('evaluation_solution_plans.id', ondelete='RESTRICT'), nullable=False)` |
| `criterion_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `weight` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `coverage_weight` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `conservative_satisfaction_numerator` | `Mapped[int]` | `mapped_column(BigInteger, nullable=False)` |
| `conservative_satisfaction_denominator` | `Mapped[int]` | `mapped_column(BigInteger, nullable=False)` |
| `optimistic_satisfaction_numerator` | `Mapped[int]` | `mapped_column(BigInteger, nullable=False)` |
| `optimistic_satisfaction_denominator` | `Mapped[int]` | `mapped_column(BigInteger, nullable=False)` |
| `contribution_conservative_numerator` | `Mapped[int]` | `mapped_column(BigInteger, nullable=False)` |
| `contribution_conservative_denominator` | `Mapped[int]` | `mapped_column(BigInteger, nullable=False)` |
| `contribution_optimistic_numerator` | `Mapped[int]` | `mapped_column(BigInteger, nullable=False)` |
| `contribution_optimistic_denominator` | `Mapped[int]` | `mapped_column(BigInteger, nullable=False)` |
| `evidence_ids` | `Mapped[list[str]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `evidence_state` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `prior_label` | `Mapped[str &#124; None]` | `mapped_column(String(120), nullable=True)` |
| `input_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `component_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'solution_plan_record_id', 'criterion_id', name='uq_score_component_criterion'), CheckConstraint('weight BETWEEN 1 AND 5', name='ck_score_component_weight'), CheckConstraint('coverage_weight BETWEEN 1 AND 5', name='ck_score_component_coverage_weight'), CheckConstraint('conservative_satisfaction_denominator > 0 AND optimistic_satisfaction_denominator > 0 AND contribution_conservative_denominator > 0 AND contribution_optimistic_denominator > 0', name='ck_score_component_denominators_positive'), CheckConstraint('conservative_satisfaction_numerator BETWEEN 0 AND conservative_satisfaction_denominator AND optimistic_satisfaction_numerator BETWEEN 0 AND optimistic_satisfaction_denominator', name='ck_score_component_satisfaction_unit_interval'), CheckConstraint("evidence_state IN ('ACCEPTABLE','UNKNOWN','STALE','CONFLICT')", name='ck_score_component_evidence_state'), Index('ix_score_components_evaluation', 'evaluation_run_id', 'criterion_id'))
```

### `seller_activity_events` — `SellerActivityEvent`

Source: `python/persistence/models.py:1688`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `product_id` | `Mapped[str]` | `mapped_column(ForeignKey('seller_products.id', ondelete='RESTRICT'), nullable=False)` |
| `event_type` | `Mapped[str]` | `mapped_column(String(40), nullable=False)` |
| `session_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `question_fingerprint` | `Mapped[str &#124; None]` | `mapped_column(String(80), nullable=True)` |
| `occurred_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |
| `fixture_label` | `Mapped[str &#124; None]` | `mapped_column(String(80), nullable=True)` |

Constraints/indexes:

```python
(CheckConstraint("event_type IN ('ANSWER_RENDERED','SELLER_HANDOFF_REQUESTED')", name='ck_seller_activity_type'), Index('ix_seller_activity_window', 'organization_id', 'product_id', 'occurred_at'))
```

### `seller_evidence_attachments` — `SellerEvidenceAttachment`

Source: `python/persistence/models.py:1495`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `draft_id` | `Mapped[str]` | `mapped_column(ForeignKey('seller_pack_drafts.id', ondelete='RESTRICT'), nullable=False)` |
| `attached_revision` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `source_reference_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `public_source_url` | `Mapped[str &#124; None]` | `mapped_column(String(500), nullable=True)` |
| `object_bucket` | `Mapped[str &#124; None]` | `mapped_column(String(255), nullable=True)` |
| `object_key` | `Mapped[str &#124; None]` | `mapped_column(String(500), nullable=True)` |
| `object_version_id` | `Mapped[str &#124; None]` | `mapped_column(String(200), nullable=True)` |
| `object_checksum` | `Mapped[str &#124; None]` | `mapped_column(String(80), nullable=True)` |
| `content_type` | `Mapped[str &#124; None]` | `mapped_column(String(120), nullable=True)` |
| `size_bytes` | `Mapped[int &#124; None]` | `mapped_column(BigInteger, nullable=True)` |
| `source_class` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `claim_fields` | `Mapped[list[str]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `observed_at` | `Mapped[datetime &#124; None]` | `mapped_column(DateTime(timezone=True), nullable=True)` |
| `verification_state` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `verification_actor_id` | `Mapped[str &#124; None]` | `mapped_column(String(100), nullable=True)` |
| `verification_method` | `Mapped[str &#124; None]` | `mapped_column(String(100), nullable=True)` |
| `added_by_actor_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint('attached_revision >= 1', name='ck_seller_evidence_revision'), CheckConstraint("verification_state IN ('UNVERIFIED','PENDING','VERIFIED','REJECTED')", name='ck_seller_evidence_verification'), CheckConstraint('(object_bucket IS NULL AND object_key IS NULL AND object_version_id IS NULL AND object_checksum IS NULL AND content_type IS NULL AND size_bytes IS NULL) OR (object_bucket IS NOT NULL AND object_key IS NOT NULL AND object_version_id IS NOT NULL AND object_checksum IS NOT NULL AND content_type IS NOT NULL AND size_bytes > 0)', name='ck_seller_evidence_object_identity'), UniqueConstraint('organization_id', 'draft_id', 'source_reference_hash', name='uq_seller_evidence_source'))
```

### `seller_pack_draft_revisions` — `SellerPackDraftRevision`

Source: `python/persistence/models.py:1462`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `draft_id` | `Mapped[str]` | `mapped_column(ForeignKey('seller_pack_drafts.id', ondelete='RESTRICT'), nullable=False)` |
| `revision` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `revision_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `claims` | `Mapped[list[dict[str, Any]]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `fit_rules` | `Mapped[list[dict[str, Any]]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `anti_fit_rules` | `Mapped[list[dict[str, Any]]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `proof_adapter` | `Mapped[dict[str, Any] &#124; None]` | `mapped_column(JSON_DOCUMENT, nullable=True)` |
| `validation` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `created_by_actor_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `frozen_at` | `Mapped[datetime &#124; None]` | `mapped_column(DateTime(timezone=True), nullable=True)` |

Constraints/indexes:

```python
(CheckConstraint('revision >= 1', name='ck_seller_draft_snapshot_revision'), UniqueConstraint('organization_id', 'draft_id', 'revision', name='uq_seller_draft_revision'), UniqueConstraint('organization_id', 'draft_id', 'revision_hash', name='uq_seller_draft_hash'))
```

### `seller_pack_drafts` — `SellerPackDraft`

Source: `python/persistence/models.py:1427`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `product_id` | `Mapped[str]` | `mapped_column(ForeignKey('seller_products.id', ondelete='RESTRICT'), nullable=False)` |
| `editor_actor_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `state` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `publisher_authority` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `current_revision` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `current_revision_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `validation` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `submitted_at` | `Mapped[datetime &#124; None]` | `mapped_column(DateTime(timezone=True), nullable=True)` |
| `frozen_at` | `Mapped[datetime &#124; None]` | `mapped_column(DateTime(timezone=True), nullable=True)` |
| `based_on_pack_version_id` | `Mapped[str &#124; None]` | `mapped_column(String(64), nullable=True)` |

Constraints/indexes:

```python
(CheckConstraint('current_revision >= 1', name='ck_seller_draft_revision'), CheckConstraint("state IN ('SELLER_DRAFT','VALIDATION_CONFLICT','IN_REVIEW','CHANGES_REQUESTED','PUBLISH_READY','PUBLISHED','SUPERSEDED','PUBLICATION_FAILED')", name='ck_seller_draft_state'), CheckConstraint("publisher_authority IN ('SELLER_SEALED','PLATFORM_COMPILED','EXTERNAL_UNSEALED')", name='ck_seller_draft_authority'), UniqueConstraint('organization_id', 'product_id', name='uq_seller_current_draft'))
```

### `seller_pack_export_artifacts` — `SellerPackExportArtifact`

Source: `python/persistence/models.py:1664`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `pack_version_id` | `Mapped[str]` | `mapped_column(ForeignKey('seller_pack_versions.id', ondelete='RESTRICT'), nullable=False)` |
| `format` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `content_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `generated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint("format IN ('JSON','HTML','REUSABLE_ANSWER')", name='ck_seller_export_format'), UniqueConstraint('organization_id', 'pack_version_id', 'format', name='uq_seller_pack_export'))
```

### `seller_pack_suspensions` — `SellerPackSuspension`

Source: `python/persistence/models.py:1644`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `pack_version_id` | `Mapped[str]` | `mapped_column(ForeignKey('seller_pack_versions.id', ondelete='RESTRICT'), nullable=False)` |
| `reason` | `Mapped[str]` | `mapped_column(String(1000), nullable=False)` |
| `effective_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |
| `actor_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `event_key` | `Mapped[str]` | `mapped_column(String(128), nullable=False)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'event_key', name='uq_seller_suspension_event'),)
```

### `seller_pack_versions` — `SellerPackVersion`

Source: `python/persistence/models.py:1610`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `product_id` | `Mapped[str]` | `mapped_column(ForeignKey('seller_products.id', ondelete='RESTRICT'), nullable=False)` |
| `source_draft_id` | `Mapped[str]` | `mapped_column(ForeignKey('seller_pack_drafts.id', ondelete='RESTRICT'), nullable=False)` |
| `source_revision` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `source_revision_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `version` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `content_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `publisher_authority` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `published_by_actor_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `published_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |
| `superseded_by_version_id` | `Mapped[str &#124; None]` | `mapped_column(String(64), nullable=True)` |

Constraints/indexes:

```python
(CheckConstraint('source_revision >= 1', name='ck_seller_pack_source_revision'), CheckConstraint('version >= 1', name='ck_seller_pack_version'), CheckConstraint("publisher_authority IN ('SELLER_SEALED','PLATFORM_COMPILED')", name='ck_seller_pack_published_authority'), UniqueConstraint('organization_id', 'product_id', 'version', name='uq_seller_pack_version'), UniqueConstraint('organization_id', 'content_hash', name='uq_seller_pack_content_hash'))
```

### `seller_product_claims` — `SellerProductClaim`

Source: `python/persistence/models.py:1390`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `product_id` | `Mapped[str]` | `mapped_column(ForeignKey('seller_products.id', ondelete='RESTRICT'), nullable=False)` |
| `claimant_actor_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `requested_role` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `authority_proof_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `state` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `safe_reason` | `Mapped[str &#124; None]` | `mapped_column(String(500), nullable=True)` |
| `decided_by_actor_id` | `Mapped[str &#124; None]` | `mapped_column(String(100), nullable=True)` |
| `decided_at` | `Mapped[datetime &#124; None]` | `mapped_column(DateTime(timezone=True), nullable=True)` |

Constraints/indexes:

```python
(CheckConstraint("requested_role IN ('SELLER_EDITOR','SELLER_REVIEWER')", name='ck_seller_claim_role'), CheckConstraint("state IN ('CLAIM_PENDING','CLAIM_DENIED','SELLER_DRAFT')", name='ck_seller_claim_state'), UniqueConstraint('organization_id', 'product_id', 'claimant_actor_id', 'authority_proof_hash', name='uq_seller_claim_proof'), Index('ix_seller_claim_product_state', 'organization_id', 'product_id', 'state'))
```

### `seller_products` — `SellerProduct`

Source: `python/persistence/models.py:1357`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `name` | `Mapped[str]` | `mapped_column(String(200), nullable=False)` |
| `category` | `Mapped[str]` | `mapped_column(String(120), nullable=False)` |
| `public_summary` | `Mapped[str]` | `mapped_column(Text, nullable=False)` |
| `publisher_authority` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `state` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `owner_actor_id` | `Mapped[str &#124; None]` | `mapped_column(String(100), nullable=True)` |
| `current_draft_id` | `Mapped[str &#124; None]` | `mapped_column(String(64), nullable=True)` |
| `current_pack_version_id` | `Mapped[str &#124; None]` | `mapped_column(String(64), nullable=True)` |
| `current_version` | `Mapped[int]` | `mapped_column(Integer, nullable=False, default=1)` |
| `fixture_label` | `Mapped[str &#124; None]` | `mapped_column(String(80), nullable=True)` |

Constraints/indexes:

```python
(CheckConstraint("publisher_authority IN ('SELLER_SEALED','PLATFORM_COMPILED','EXTERNAL_UNSEALED')", name='ck_seller_product_authority'), CheckConstraint("state IN ('UNCLAIMED','CLAIM_PENDING','CLAIM_DENIED','SELLER_DRAFT','VALIDATION_CONFLICT','IN_REVIEW','CHANGES_REQUESTED','PUBLISH_READY','PUBLISHED','SUPERSEDED','PUBLICATION_FAILED')", name='ck_seller_product_state'), CheckConstraint('current_version >= 1', name='ck_seller_product_version'), UniqueConstraint('organization_id', 'name', 'category', name='uq_seller_product_identity'))
```

### `seller_review_decisions` — `SellerReviewDecisionRecord`

Source: `python/persistence/models.py:1574`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `submission_id` | `Mapped[str]` | `mapped_column(ForeignKey('seller_review_submissions.id', ondelete='RESTRICT'), nullable=False)` |
| `draft_id` | `Mapped[str]` | `mapped_column(ForeignKey('seller_pack_drafts.id', ondelete='RESTRICT'), nullable=False)` |
| `decision` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `revision_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `actor_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `actor_role` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `reason` | `Mapped[str]` | `mapped_column(String(1000), nullable=False)` |
| `event_key` | `Mapped[str]` | `mapped_column(String(128), nullable=False)` |
| `occurred_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |

Constraints/indexes:

```python
(CheckConstraint("decision IN ('REQUEST_CHANGES','APPROVE','REJECT')", name='ck_seller_review_decision'), CheckConstraint("actor_role IN ('SELLER_REVIEWER','PLATFORM_OPERATOR')", name='ck_seller_review_actor_role'), UniqueConstraint('organization_id', 'event_key', name='uq_seller_review_event'), UniqueConstraint('organization_id', 'submission_id', name='uq_seller_review_final_decision'))
```

### `seller_review_submissions` — `SellerReviewSubmission`

Source: `python/persistence/models.py:1544`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `draft_id` | `Mapped[str]` | `mapped_column(ForeignKey('seller_pack_drafts.id', ondelete='RESTRICT'), nullable=False)` |
| `revision` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `revision_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `submitted_by_actor_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `reviewer_role` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `status` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `submitted_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), nullable=False)` |
| `completed_at` | `Mapped[datetime &#124; None]` | `mapped_column(DateTime(timezone=True), nullable=True)` |

Constraints/indexes:

```python
(CheckConstraint('revision >= 1', name='ck_seller_review_revision'), CheckConstraint("reviewer_role IN ('SELLER_REVIEWER','PLATFORM_OPERATOR')", name='ck_seller_review_role'), CheckConstraint("status IN ('PENDING','COMPLETED')", name='ck_seller_review_status'), UniqueConstraint('organization_id', 'draft_id', 'revision_hash', name='uq_seller_review_submission'))
```

### `solution_plan_components` — `SolutionPlanComponent`

Source: `python/persistence/models.py:510`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `evaluation_run_id` | `Mapped[str]` | `mapped_column(ForeignKey('evaluation_runs.id', ondelete='RESTRICT'), nullable=False)` |
| `solution_plan_record_id` | `Mapped[str]` | `mapped_column(ForeignKey('evaluation_solution_plans.id', ondelete='RESTRICT'), nullable=False)` |
| `component_id` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` |
| `ordinal` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `source_type` | `Mapped[str]` | `mapped_column(String(40), nullable=False)` |
| `action` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `source_record_id` | `Mapped[str &#124; None]` | `mapped_column(String(128), nullable=True)` |
| `component_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'solution_plan_record_id', 'component_id', name='uq_solution_plan_component'), UniqueConstraint('organization_id', 'solution_plan_record_id', 'ordinal', name='uq_solution_plan_component_ordinal'), CheckConstraint('ordinal >= 0', name='ck_solution_plan_component_ordinal_nonnegative'), CheckConstraint("action IN ('REUSE_EXISTING','CONFIGURE_EXISTING','NO_ACTION','BUY','RENEW','RESIZE','REPLACE','CONSOLIDATE','CANCEL')", name='ck_solution_plan_component_action'), CheckConstraint("source_type IN ('PACK','CURRENT_STACK','CONTRACT_ACTION','NO_ACTION')", name='ck_solution_plan_component_source_type'), Index('ix_solution_plan_components_evaluation', 'evaluation_run_id'))
```

### `stack_patches` — `StackPatch`

Source: `python/persistence/models.py:1344`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `base_snapshot_id` | `Mapped[str]` | `mapped_column(ForeignKey('stack_snapshots.id', ondelete='RESTRICT'), nullable=False)` |
| `base_version` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `state` | `Mapped[str]` | `mapped_column(String(32), nullable=False)` |
| `payload` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `patch_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |

### `stack_snapshots` — `StackSnapshot`

Source: `python/persistence/models.py:1329`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `version` | `Mapped[int]` | `mapped_column(Integer, nullable=False)` |
| `manifest` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `lock` | `Mapped[dict[str, Any]]` | `mapped_column(JSON_DOCUMENT, nullable=False)` |
| `lock_hash` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'version', name='uq_stack_snapshot_version'), UniqueConstraint('organization_id', 'lock_hash', name='uq_stack_lock_hash'))
```

### `workflow_runs` — `WorkflowRun`

Source: `python/persistence/models.py:2515`.

| Field | Mapped type | SQL declaration |
|---|---|---|
| `organization_id` | `Mapped[str]` | `mapped_column(String(64), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False, index=True)` |
| `created_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)` |
| `updated_at` | `Mapped[datetime]` | `mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` |
| `id` | `Mapped[str]` | `mapped_column(String(64), primary_key=True)` |
| `aggregate_type` | `Mapped[str]` | `mapped_column(String(80), nullable=False)` |
| `aggregate_id` | `Mapped[str]` | `mapped_column(String(64), nullable=False)` |
| `operation` | `Mapped[str]` | `mapped_column(String(120), nullable=False)` |
| `status` | `Mapped[str]` | `mapped_column(String(24), nullable=False)` |
| `result_reference` | `Mapped[str &#124; None]` | `mapped_column(String(160), nullable=True)` |
| `safe_error_code` | `Mapped[str &#124; None]` | `mapped_column(String(80), nullable=True)` |
| `event_log` | `Mapped[list[dict[str, Any]]]` | `mapped_column(JSON_DOCUMENT, nullable=False, default=list)` |

Constraints/indexes:

```python
(UniqueConstraint('organization_id', 'aggregate_type', 'aggregate_id', 'operation', name='uq_workflow_identity'), CheckConstraint("status IN ('PENDING','RUNNING','COMPLETED','FAILED')", name='ck_workflow_status'))
```

Total ORM tables: **99**.

### Migration chain

- `cdb0001_cockroach_baseline.py`: cockroach baseline
- `cdb0002_tenant_rls.py`: Enforce tenant isolation for the CockroachDB runtime role.
- `cdb0003_qualified_marketplace_kernel.py`: qualified marketplace kernel
- `cdb0004_marketplace_search_inputs.py`: marketplace search and mission inputs
- `cdb0005_attempt_scoped_bundles.py`: attempt-scoped bundles and buyer-safe engagement projection
- `cdb0006_bilateral_responses.py`: make seller responses readable by both verified parties
- `cdb0007_active_bundle_verification.py`: allow runtime verification of public active bundle pointers
- `cdb0008_company_context_memory.py`: add versioned private company context
- `cdb0009_versioned_seller_evidence_objects.py`: bind seller evidence to immutable versioned object identities
- `cdb0010_workspace_settings.py`: add versioned workspace notification and disclosure settings
- `cdb0011_hosted_tenant_roles.py`: add narrow hosted tenant bootstrap and worker discovery roles
- `cdb0012_payment_handoff.py`: replace legacy checkout execution with a provider-neutral payment handoff
- `cdb0013_cognitive_runtime_journal.py`: add durable cognitive runtime journal
- `cdb0014_runtime_ticket_replay.py`: add single-use runtime ticket replay guard
- `cdb0015_bilateral_exchange_isolation.py`: add append-only bilateral exchange and split service roles
- `cdb0016_evidence_spans.py`: add immutable evidence sources and distributed vector spans
- `cdb0017_exchange_contracts.py`: add exact disclosure envelopes and immutable offer versions
- `cdb0018_bilateral_handoffs.py`: add exact provider-neutral bilateral payment handoffs

## Appendix F. Dependencies, runtime settings and semantic validator references

### `package.json`

```json
{
  "packageManager": "pnpm@11.9.0",
  "engines": {
    "node": ">=22.0.0"
  },
  "devDependencies": {
    "@axe-core/playwright": "4.10.2",
    "@playwright/test": "1.55.0",
    "prettier": "3.6.2",
    "typescript": "5.9.2"
  }
}
```

### `apps/web/package.json`

```json
{
  "dependencies": {
    "@chenglou/pretext": "^0.0.8",
    "@sira/api-client": "workspace:*",
    "@tanstack/react-query": "5.101.4",
    "class-variance-authority": "0.7.1",
    "clsx": "2.1.1",
    "firebase": "^12.17.0",
    "lucide-react": "1.28.0",
    "next": "16.2.12",
    "react": "19.2.8",
    "react-dom": "19.2.8",
    "tailwind-merge": "3.6.0"
  },
  "devDependencies": {
    "@tailwindcss/postcss": "4.3.3",
    "@types/node": "26.1.2",
    "@types/react": "19.2.18",
    "@types/react-dom": "19.2.4",
    "eslint": "9.39.5",
    "eslint-config-next": "16.2.12",
    "tailwindcss": "4.3.3",
    "typescript": "6.0.3"
  }
}
```

### `packages/api-client/package.json`

```json
{
  "devDependencies": {
    "typescript": "5.9.2"
  }
}
```

### `infra/aws/package.json`

```json
{
  "dependencies": {
    "aws-cdk-lib": "2.264.0",
    "constructs": "10.8.1"
  },
  "devDependencies": {
    "@types/node": "26.1.2",
    "aws-cdk": "2.1136.0",
    "tsx": "4.20.6",
    "typescript": "5.9.2"
  }
}
```

### Python direct dependency specifications

```text
alembic>=1.16,<2
asyncpg>=0.30,<1
boto3>=1.43,<2
botocore[crt]>=1.43,<2
cryptography>=45,<47
fastapi>=0.116,<1
greenlet>=3.2,<4
httpx>=0.28,<1
mcp>=1.29,<2
psycopg[binary]>=3.2,<4
pydantic-settings>=2.10,<3
pydantic>=2.11,<3
python-multipart>=0.0.20,<1
pyjwt[crypto]>=2.10,<3
pyyaml>=6.0,<7
rfc8785>=0.1.4,<1
sqlalchemy[asyncio]>=2.0,<2.1
sqlalchemy-cockroachdb>=2.0,<3
uvicorn[standard]>=0.35,<1
```

### Python resolved direct dependencies from uv.lock

| Package | Resolved version |
|---|---|
| `alembic` | `1.18.5` |
| `asyncpg` | `0.31.0` |
| `boto3` | `1.43.70` |
| `botocore` | `1.43.70` |
| `cryptography` | `46.0.0` |
| `fastapi` | `0.141.1` |
| `greenlet` | `3.5.4` |
| `httpx` | `0.28.1` |
| `mcp` | `1.29.0` |
| `psycopg` | `3.3.4` |
| `pydantic` | `2.13.4` |
| `pydantic-settings` | `2.14.2` |
| `pyjwt` | `2.13.0` |
| `python-multipart` | `0.0.32` |
| `pyyaml` | `6.0.3` |
| `rfc8785` | `0.1.4` |
| `sqlalchemy` | `2.0.51` |
| `sqlalchemy-cockroachdb` | `2.0.4` |
| `uvicorn` | `0.52.1` |

For JS transitive versions and range resolutions, preserve `pnpm-lock.yaml` in full.

### `ApiSettings` configuration

Source: `services/api/sira_api/config.py`. Defaults below are source defaults, not production-safe configuration. SecretStr entries describe declarations only; no local environment or credential contents were read.

| Setting | Type | Default / validation / environment alias |
|---|---|---|
| `app_env` | `str` | `Field(default='unset', validation_alias='APP_ENV')` |
| `log_level` | `str` | `Field(default='INFO', validation_alias='LOG_LEVEL')` |
| `development_fixture_mode` | `bool` | `Field(default=True, validation_alias='DEVELOPMENT_FIXTURE_MODE')` |
| `demo_reset_enabled` | `bool` | `Field(default=True, validation_alias='DEMO_RESET_ENABLED')` |
| `guest_session_enabled` | `bool` | `Field(default=False, validation_alias='GUEST_SESSION_ENABLED')` |
| `guest_session_signing_key` | `SecretStr` | `Field(default=SecretStr(''), validation_alias='GUEST_SESSION_SIGNING_KEY')` |
| `guest_session_ttl_seconds` | `int` | `Field(default=604800, ge=3600, le=2592000, validation_alias='GUEST_SESSION_TTL_SECONDS')` |
| `public_base_url` | `str` | `Field(default='http://localhost:8000', validation_alias='PUBLIC_BASE_URL')` |
| `web_base_url` | `str` | `Field(default='http://localhost:3000', validation_alias='WEB_BASE_URL')` |
| `database_url` | `str` | `Field(default='cockroachdb+asyncpg://sira_app@127.0.0.1:26257/sira?ssl=disable', validation_alias='DATABASE_URL')` |
| `catalog_database_url` | `SecretStr` | `Field(default=SecretStr(''), validation_alias='SIRA_CATALOG_DATABASE_URL')` |
| `identity_introspection_url` | `str` | `Field(default='', validation_alias='IDENTITY_INTROSPECTION_URL')` |
| `identity_client_id` | `str` | `Field(default='', validation_alias='IDENTITY_CLIENT_ID')` |
| `identity_client_secret` | `SecretStr` | `Field(default=SecretStr(''), validation_alias='IDENTITY_CLIENT_SECRET')` |
| `identity_expected_issuer` | `str` | `Field(default='', validation_alias='IDENTITY_EXPECTED_ISSUER')` |
| `identity_expected_audience` | `str` | `Field(default='', validation_alias='IDENTITY_EXPECTED_AUDIENCE')` |
| `identity_allowed_roles` | `str` | `Field(default='', validation_alias='IDENTITY_ALLOWED_ROLES')` |
| `identity_step_up_acr_values` | `str` | `Field(default='', validation_alias='IDENTITY_STEP_UP_ACR_VALUES')` |
| `identity_step_up_max_age_seconds` | `int` | `Field(default=600, ge=60, le=3600, validation_alias='IDENTITY_STEP_UP_MAX_AGE_SECONDS')` |
| `firebase_project_id` | `str` | `Field(default='', validation_alias='FIREBASE_PROJECT_ID')` |
| `aws_region` | `str` | `Field(default='us-east-1', validation_alias=AliasChoices('AWS_REGION', 'AWS_DEFAULT_REGION'))` |
| `aws_profile` | `str` | `Field(default='', validation_alias='AWS_PROFILE')` |
| `agent_runtime_provider` | `Literal['agentcore', 'bedrock']` | `Field(default='bedrock', validation_alias='AGENT_RUNTIME_PROVIDER')` |
| `cognitive_kernel_enabled` | `bool` | `Field(default=True, validation_alias='COGNITIVE_KERNEL_ENABLED')` |
| `principal_isolation_enabled` | `bool` | `Field(default=True, validation_alias='PRINCIPAL_ISOLATION_ENABLED')` |
| `sira_agentcore_runtime_arn` | `str` | `Field(default='', validation_alias='SIRA_AGENTCORE_RUNTIME_ARN')` |
| `seil_agentcore_runtime_arn` | `str` | `Field(default='', validation_alias='SEIL_AGENTCORE_RUNTIME_ARN')` |
| `runtime_ticket_signing_key` | `SecretStr` | `Field(default=SecretStr(''), validation_alias='RUNTIME_TICKET_SIGNING_KEY')` |
| `bedrock_chat_model_id` | `str` | `Field(default='us.amazon.nova-2-lite-v1:0', validation_alias='BEDROCK_CHAT_MODEL_ID')` |
| `bedrock_embedding_model_id` | `str` | `Field(default='amazon.titan-embed-text-v2:0', validation_alias='BEDROCK_EMBEDDING_MODEL_ID')` |
| `bedrock_guardrail_id` | `str` | `Field(default='', validation_alias='BEDROCK_GUARDRAIL_ID')` |
| `bedrock_guardrail_version` | `str` | `Field(default='DRAFT', validation_alias='BEDROCK_GUARDRAIL_VERSION')` |
| `s3_evidence_bucket` | `str` | `Field(default='', validation_alias='SIRA_S3_EVIDENCE_BUCKET')` |
| `s3_evidence_kms_key_id` | `str` | `Field(default='', validation_alias='SIRA_S3_EVIDENCE_KMS_KEY_ID')` |
### `WorkerSettings` configuration

Source: `services/worker/sira_worker/runtime.py`. Defaults below are source defaults, not production-safe configuration. SecretStr entries describe declarations only; no local environment or credential contents were read.

| Setting | Type | Default / validation / environment alias |
|---|---|---|
| `worker_mode` | `Literal['dispatcher', 'qualification', 'changefeed']` | `Field(default='qualification', validation_alias='SIRA_WORKER_MODE')` |
| `worker_database_url` | `SecretStr` | `Field(validation_alias='SIRA_WORKER_DATABASE_URL')` |
| `catalog_database_url` | `SecretStr` | `Field(default=SecretStr(''), validation_alias='SIRA_CATALOG_DATABASE_URL')` |
| `organization_ids` | `Annotated[tuple[str, ...], NoDecode]` | `Field(default=(), validation_alias='WORKER_ORGANIZATION_IDS')` |
| `aws_region` | `str` | `Field(default='us-east-1', validation_alias='AWS_REGION')` |
| `aws_profile` | `str &#124; None` | `Field(default=None, validation_alias='AWS_PROFILE')` |
| `queue_url` | `str` | `Field(validation_alias='SIRA_SQS_QUEUE_URL')` |
| `chat_model_id` | `str` | `Field(default='us.amazon.nova-2-lite-v1:0', validation_alias='BEDROCK_CHAT_MODEL_ID')` |
| `embedding_model_id` | `str` | `Field(default='amazon.titan-embed-text-v2:0', validation_alias='BEDROCK_EMBEDDING_MODEL_ID')` |
| `guardrail_id` | `str` | `Field(default='', validation_alias='BEDROCK_GUARDRAIL_ID')` |
| `guardrail_version` | `str` | `Field(default='DRAFT', validation_alias='BEDROCK_GUARDRAIL_VERSION')` |
| `log_level` | `str` | `Field(default='INFO', validation_alias='LOG_LEVEL')` |
| `idle_delay_seconds` | `float` | `Field(default=2.0, ge=0.1, le=30)` |
| `app_env` | `Literal['development', 'test', 'production']` | `Field(default='development', validation_alias='APP_ENV')` |

### Pydantic semantic validators (beyond JSON Schema)

Reimplement these functions when cloning their model. Custom validators enforce relationships between fields which the generated JSON Schema does not fully capture.

- `RequirementBriefCreate.exact_visible_requirements` — `services/api/sira_api/qualification_schemas.py:49`; `field_validator('seller_visible_requirements')`
- `QualificationMissionCreate.exact_private_inputs` — `services/api/sira_api/qualification_schemas.py:64`; `field_validator('buyer_context', 'procurement_policy')`
- `QualificationMissionCreate.unique_context_items` — `services/api/sira_api/qualification_schemas.py:69`; `field_validator('company_context_item_ids')`
- `CompanyContextCreate.exact_payload` — `services/api/sira_api/qualification_schemas.py:83`; `field_validator('payload')`
- `CompanyContextUpdate.exact_payload` — `services/api/sira_api/qualification_schemas.py:96`; `field_validator('payload')`
- `QualificationSellerResponseCreate.unique_citations` — `services/api/sira_api/qualification_schemas.py:172`; `field_validator('cited_evidence_ids')`
- `QualificationConsentCreate.exact_shared_fields` — `services/api/sira_api/qualification_schemas.py:183`; `field_validator('shared_fields')`
- `ProductEvidenceComponent.one_component_source` — `services/api/sira_api/schemas_v2.py:263`; `model_validator(mode='after')`
- `ApprovalProjection.not_required_is_empty` — `services/api/sira_api/schemas_v2.py:378`; `model_validator(mode='after')`
- `DecisionComponentResult.one_component_source` — `services/api/sira_api/schemas_v2.py:521`; `model_validator(mode='after')`
- `ActionRunView.completed_run_has_proof` — `services/api/sira_api/schemas_v2.py:762`; `model_validator(mode='after')`

### Frozen domain documents

- `action-run.schema.json`: required top-level fields `["schema_version","action_run_id","workflow_id","decision_id","decision_version","decision_hash","selection_id","solution_plan_id","action_type","status","current_step_id","last_successful_checkpoint_id","owner_role","blocking_task","recovery_action","execution_steps","payment_handoff","result_artifacts","created_at","updated_at","completed_at"]`; definitions and nested constraints remain in the corresponding frozen schema.
- `approval-plan.schema.json`: required top-level fields `["schema_version","approval_requirement_set_id","policy_version","stages","cardholder_authentication_separate","content_hash"]`; definitions and nested constraints remain in the corresponding frozen schema.
- `approval.schema.json`: required top-level fields `["schema_version","approval_request_id","purchase_intent_id","intent_hash","status","policy_version","requirement_set_id","stages","exact_summary","created_at","expires_at"]`; definitions and nested constraints remain in the corresponding frozen schema.
- `buyer-passport.schema.json`: required top-level fields `["schema_version","passport_id","organization_id","version","company_profile","facts","stakeholders","budget","operational_preferences","created_at"]`; definitions and nested constraints remain in the corresponding frozen schema.
- `calibration.schema.json`: required top-level fields `["schema_version","calibration_run_id","request_id","base_purchase_brief_id","base_purchase_brief_version","examples","proposal","ranking_effect","created_at"]`; definitions and nested constraints remain in the corresponding frozen schema.
- `common.schema.json`: required top-level fields `[]`; definitions and nested constraints remain in the corresponding frozen schema.
- `decision-ledger.schema.json`: required top-level fields `["schema_version","decision_id","decision_version","decision_state","supersedes_decision_id","request_id","purchase_brief_id","purchase_brief_version","requirement_brief_id","requirement_brief_version","company_profile_version","stack_snapshot","policy_version","evaluation","evaluated_universe","component_results","solution_plans","decision_outcome","selected_solution_plan_id","rank_stability","counterfactuals","decision_hash","created_at"]`; definitions and nested constraints remain in the corresponding frozen schema.
- `decision-view.schema.json`: required top-level fields `["request","workflow","evaluation","company_context","disclosure_preview","coverage","decision_outcome","rank_stability","solution_options","selected_action_plan","stack_change","approval","payment_handoff","result_artifacts"]`; definitions and nested constraints remain in the corresponding frozen schema.
- `engagement.schema.json`: required top-level fields `["schema_version","engagement_id","decision_request_id","decision_version","solution_plan_id","visibility","action","status","requirement_brief_id","requirement_brief_version","buyer_identity_disclosed","seller_identity_disclosed","buyer_contact","seller_contact","buyer_consent","seller_consent","created_at"]`; definitions and nested constraints remain in the corresponding frozen schema.
- `enums.schema.json`: required top-level fields `[]`; definitions and nested constraints remain in the corresponding frozen schema.
- `evidence-bundle.schema.json`: required top-level fields `["schema_version","evidence"]`; definitions and nested constraints remain in the corresponding frozen schema.
- `offer.schema.json`: required top-level fields `[]`; definitions and nested constraints remain in the corresponding frozen schema.
- `procurement-plan.schema.json`: required top-level fields `["schema_version","procurement_plan_id","request_id","decision_id","version","gates","evaluated_at","gate_result_hash"]`; definitions and nested constraints remain in the corresponding frozen schema.
- `product-passport.schema.json`: required top-level fields `["schema_version","product_passport_id","seller_id","product_id","version","public_identity","source_material","roadmap_notes","availability_capacity","private_negotiation_bounds","fulfillment_operations","approved_positioning_library","unpublished_constraints","pack_source","publication_allowlist","compilation_history","created_at"]`; definitions and nested constraints remain in the corresponding frozen schema.
- `purchase-brief.schema.json`: required top-level fields `["schema_version","purchase_brief_id","request_id","organization_id","version","supersedes_version","status","visibility","intent","category_id","desired_outcome","stakeholder_roles","hard_gates","preferences","known_alternatives","stackfile_impact_policy","disclosure_choices","approval_requirements","calibration_examples","created_at","content_hash"]`; definitions and nested constraints remain in the corresponding frozen schema.
- `purchase-intent.schema.json`: required top-level fields `["schema_version","purchase_intent_id","organization_id","decision_id","decision_version","decision_hash","selection_id","solution_plan_id","stack_patch_id","purchase_intent_group_id","procurement_plan_id","procurement_gate_result_hash","pack_id","pack_version","offer_id","offer_version","quote_id","quote_version","quote_expires_at","merchant","approved_merchant_chain_id","amount","currency","line_items","expected_fulfillments","fulfillment_completion_policy","buyer_legal_entity_id","seller_contracting_entity_id","billing_identity_id","cost_center_id","purchase_order_ref","merchant_subtotal","tax_amount","fee_amount","fee_schedule_version","landed_total","approval_policy_version","approval_requirement_set_id","approval_plan_hash","intent_hash","locked_at"]`; definitions and nested constraints remain in the corresponding frozen schema.
- `requirement-brief.schema.json`: required top-level fields `["schema_version","requirement_brief_id","purchase_brief_id","purchase_brief_version","version","visibility","category_id","intent","desired_outcome","team","data_profile","hard_requirements","preferences","allowed_stack_context","seller_questions","expires_at","content_hash"]`; definitions and nested constraints remain in the corresponding frozen schema.
- `seil-pack.schema.json`: required top-level fields `["schema_version","pack_id","version","status","seller_id","product_id","identity","offer_ids","category_ids","jtbd_ids","facts","fit_rules","anti_fit_rules","dependency_rules","positioning_angles","claims","commercial","fulfillment_spec","merchant_chain","operations","published_at","supersedes_version","content_hash"]`; definitions and nested constraints remain in the corresponding frozen schema.
- `seller-evidence-view.schema.json`: required top-level fields `["product","actor","publisher_authority","pack_health","validation","review","reusable_answers","activity_metrics","available_actions","version_links"]`; definitions and nested constraints remain in the corresponding frozen schema.
- `stack-patch.schema.json`: required top-level fields `["schema_version","patch_id","organization_id","base_snapshot","decision_id","solution_plan_id","status","operations","prerequisites","rollback_plan","cost_impact","risk","expected_outcome","created_at","content_hash"]`; definitions and nested constraints remain in the corresponding frozen schema.
- `stackfile-lock.schema.json`: required top-level fields `["schema_version","organization_id","snapshot","generated_at","manifest_hash","instances","edges","content_hash"]`; definitions and nested constraints remain in the corresponding frozen schema.

### Operational and acceptance reference map

| Concern | Source |
|---|---|
| Architecture boundaries | `tests/unit/test_architecture_boundaries.py` |
| Tenant and production guards | `tests/api/test_production_boundaries.py; tests/unit/test_database_readiness.py` |
| Decision arithmetic/rules | `tests/unit/test_domain_rules.py; tests/unit/test_decision_bounds.py; tests/property` |
| Replay and graph fidelity | `tests/unit/test_replay_fidelity.py; tests/integration/test_decision_source_snapshots.py; tests/integration/test_decision_graph_persistence.py` |
| Seller lifecycle | `tests/api/test_seller_evidence_api.py; tests/unit/test_domain_publication.py` |
| Bilateral privacy/concurrency | `tests/unit/test_bilateral_exchange.py; tests/cockroach_integration/test_bilateral_races.py` |
| Worker recovery | `tests/unit/test_qualification_worker_runtime.py; tests/unit/test_qualification_queue_consumer.py; tests/unit/test_outbox_dispatcher.py; tests/cockroach_integration/test_qualification_kernel.py` |
| Payment authority | `tests/api/test_payment_handoff_api.py; tests/unit/test_approval_state_machine.py` |
| Agent boundaries | `tests/unit/test_agent_authority.py; tests/unit/test_cognitive_kernel.py; tests/unit/test_runtime_ticket.py; tests/integration/test_runtime_ticket_replay.py` |
| Browser parity | `tests/browser/p0-routes.spec.ts; docs/screenshots` |
| Deployment/recovery | `infra/aws/lib/sira-aws-stack.ts; docs/hackathon-build/OPERATIONS.md; python/integrations/deployment_preflight.py; python/persistence/restore_drill.py` |
| Threat/provenance | `docs/threat-model.md; SOURCE_PROVENANCE.md; LICENSE` |
