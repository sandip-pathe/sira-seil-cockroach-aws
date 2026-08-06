<!-- /autoplan restore point: C:\Users\sandi\.gstack\projects\siel-n-sira\snowflake-hackathon-autoplan-restore-20260806-060832.md -->
# SIRA + SEIL Snowflake Hackathon Plan

Date: 6 August 2026
Status: Decision-ready; implementation has not started
Chosen architecture: FastAPI-orchestrated Snowflake Decision Evidence Plane
Selected challenge: Unstructured Data Intelligence System

> Deadline warning: the current Hack2Skill and YourStory event pages show prototype submissions ending 6 August 2026, but the linked Official Rules still say 2 August 2026 at 11:59 PM IST and state that the rules control. Treat the portal as fragile: verify that it accepts the entry and capture the receipt before spending the day on optional work. The public extension has no verified cutoff time.

## 1. Problem statement and pitch

### Recommended problem statement

Software buying agents cannot make trustworthy company-specific recommendations from generic product catalogs. The buyer's decisive constraints are private, seller claims are often unstructured or qualified by limitations, and an LLM answer alone cannot prove why an option won or who approved it.

SIRA + SEIL will prove a narrower, defensible capability:

- SIRA evaluates a purchase using private, versioned company facts.
- SEIL contributes seller-controlled evidence and explicit limitations.
- Snowflake parses and retrieves the evidence, executes the deterministic evaluator, and records the exact inputs, citations, result, and approval.
- The existing product interface shows the outcome without exposing private buyer context to the seller.

### One-sentence pitch

**SIRA + SEIL turns private buyer constraints and seller-controlled documents into deterministic, cited, approval-ready procurement decisions, with Snowflake as the governed evidence and audit plane.**

### Required causal proof

The complete demo is not “data stored in Snowflake.” It must visibly prove:

1. Product A is cheaper and appears acceptable without private context.
2. A governed buyer fact says HubSpot is mandatory for this company.
3. A seller PDF says Product A supports HubSpot only on a tier above the buyer's budget.
4. Snowflake parses and retrieves that exact limitation.
5. The Snowpark evaluator marks Product A PASS/ineligible and selects Product B.
6. Re-running without the private fact changes the winner to Product A.
7. Each run has a cited explanation, frozen input hash, decision hash, and application-append-only approval record.

This is the product wedge: **evidence-to-decision causality**, not a generic marketplace, chatbot, or RAG demo.

## 2. Current architecture versus target architecture

### What exists and should be preserved

| Layer | Current reality | Repository evidence |
|---|---|---|
| Product shell | Next.js SIRA/SEIL workspace with chat, product cards, mission artifacts, proposal confirmation, and a third-panel inspector | apps/web/components/workspace/commerce-workspace.tsx:1651-1752, 1844-1856, 2309-2411 |
| Identity | Firebase anonymous, Google, and email flows; verified server-side identity maps to isolated organization IDs | apps/web/components/auth/firebase-auth-provider.tsx:40-89; services/api/sira_api/identity.py:49-103, 137-172 |
| Agent runtime | OpenAI Agents SDK with typed output and an allowlisted tool registry; protected actions remain server-owned | python/agents/sira_agents/runtime.py:44-54, 97-235 |
| Deterministic authority | Pure Python recall, evidence assessment, gates, ranking, counterfactuals, and stable hashes | python/decision_engine/graph_v1.py:1499-1704 |
| Typed source seam | DecisionSourceBundle round-trips and compiles into DecisionGraphInput | python/decision_engine/graph_v1_fixtures.py:62-105, 926-997 |
| Current audit model | Stable graph ledger plus exact intent-bound approval events | services/api/sira_api/graph_ledger.py:241-444; python/persistence/models.py:1296-1344 |
| Current persistence | PostgreSQL stores missions, source snapshots, decisions, evidence, and approvals | python/persistence/models.py; python/persistence/mission_repository.py |
| Current demo data | Fixed ConsultCo/meeting-intelligence fixture, hard-coded product overlays, and browser fixture responses | README.md:27-31; services/api/sira_api/workspace_service.py:38-121; apps/web/components/workspace/commerce-workspace.tsx:144-203 |
| Current live boundary | Discovery rejects arbitrary scenarios; seller evidence stores references rather than document bytes and cited spans | services/api/sira_api/service.py:855-929; services/api/sira_api/seller_schemas.py:186-197 |
| Snowflake | No existing Snowflake, Snowpark, Cortex Search, Streamlit, AI_PARSE_DOCUMENT, or CoCo implementation | Repository-wide audit on 6 August 2026 |

Current flow:

    Next.js /sira and /seil
        -> FastAPI WorkspaceService / WorkflowService
        -> fixture catalog + OpenAI agent
        -> deterministic Python evaluator
        -> PostgreSQL missions, decisions, approvals
        -> optional Temporal / Prava / Senso paths

Target P0 flow:

    User in existing Next.js workspace
        -> FastAPI explicit orchestrator
            -> governed Snowflake buyer facts, products, and offers
            -> seller PDF in internal stage
                -> AI_PARSE_DOCUMENT
                -> page-aware chunks
                -> Cortex Search evidence retrieval
                -> reviewer-bound structured claim
            -> frozen Snowflake input snapshot
            -> Snowpark RUN_SIRA_DECISION(request_id)
                -> existing deterministic evaluator
                -> decision + reason codes + counterfactual
            -> decision, citations, and approval ledger in Snowflake
        -> existing chat response + on-demand third-panel artifact

PostgreSQL remains the mission/authentication store. For this hackathon decision slice, Snowflake is authoritative for evaluated input snapshots, cited decision runs, and approval events. Do not dual-write two competing authoritative decisions.

### Architectures evaluated

| Candidate | Technical | Relevance | Completeness | Estimated P0 | Decision |
|---|---:|---:|---:|---:|---|
| **A. FastAPI-orchestrated Snowflake Decision Evidence Plane** | 38/40 | 29/30 | 28/30 | 6.5-8 hours | **Choose** |
| B. Cortex Agent-first orchestration with Search, Analyst, and custom evaluator tool | 34/40 | 29/30 | 23/30 | 10-12 hours | Reject for today: nondeterministic tool routing, citation, RBAC, REST, and recovery risk |
| C. Streamlit-first Snowflake application | 31/40 | 25/30 | 27/30 | 5-7 hours | Reject: sacrifices the differentiated interface and looks like a generic analytics/RAG demo |

Architecture A is exactly one runtime architecture: FastAPI controls the workflow, Snowflake supplies governed facts/evidence and executes the deterministic evaluator, and the LLM can phrase the already-authoritative result. Cortex Agent, Analyst, and Streamlit are not runtime dependencies in P0.

### Authority rules

- Search may retrieve evidence; it cannot rank products.
- A model may summarize a decision; it cannot create eligibility, PASS/FAIL, approval, or citation IDs.
- Only schema-valid seller claim bindings tied to an exact parsed chunk may reach the evaluator.
- The evaluator's structured output and hashes are authoritative.
- Approval is a separate human action bound to the exact decision hash.
- Seller Search indexes seller evidence only. Private buyer facts are queried from governed tables and are never placed in the seller search index.
- Failure is explicit. Missing evidence becomes UNKNOWN/INSUFFICIENT_EVIDENCE, never a silent pass.

### Explicitly not in scope

- Prava or any payment execution
- Temporal orchestration
- Full marketplace migration
- PostgreSQL replacement
- General-purpose procurement across arbitrary categories
- New standalone decision, payment, or audit screens
- Production-grade multi-tenant Snowflake row policies
- Cortex Agent, Analyst, Marketplace packaging, or Streamlit before the causal demo is complete

## 3. Exact Snowflake objects required

Use one database, three schemas, one Gen1 Standard X-Small warehouse, and two narrowly scoped roles.

### Account and compute

| Object | Purpose and required settings |
|---|---|
| Role SIRA_SF_BUILD_ROLE | Creates objects and performs the CoCo build. Not used by the application. |
| Role SIRA_SF_APP_ROLE | Runtime least-privilege role. Read governed/evidence projections; insert requests, runs, citations, and approval events; no UPDATE or DELETE on the approval ledger. |
| Warehouse SIRA_HACK_XS_WH | X-Small, single cluster, AUTO_SUSPEND=60 seconds, AUTO_RESUME=true, no scheduled tasks. |
| Resource monitor SIRA_HACK_WH_MONITOR | Warehouse-only guardrail: alerts at 25/50/75 percent of a 10-credit quota and suspends at 100 percent. Cortex/serverless use must be monitored separately. |
| Database SIRA_HACKATHON | Single database for the fixed prototype. |
| Schemas GOVERNED, EVIDENCE, DECISION | Buyer/catalog facts; seller documents/search; decision execution/audit. |

### Governed structured data

| Object | Minimum contract |
|---|---|
| GOVERNED.COMPANIES | company_id, name, created_at |
| GOVERNED.COMPANY_FACTS | fact_id, company_id, context_version, fact_key, typed_value VARIANT, visibility, source_kind, source_ref, valid_from, inserted_at |
| GOVERNED.STACKFILE_FACTS | stack_fact_id, company_id, context_version, product_key, status, source_ref, inserted_at |
| GOVERNED.PRODUCTS | product_id, seller_id, name, category, product_version, status |
| GOVERNED.OFFERS | offer_id, product_id, tier, unit_price, billing_unit, currency, min_seats, max_seats, effective_at |
| GOVERNED.V_CURRENT_BUYER_CONTEXT | Version-resolved facts for one company and scenario; only the app/build roles receive access |

The demo fact is CRM_SYNC_REQUIRED=true with CURRENT_CRM=HubSpot. Two context versions must exist so the before/after run changes one variable without mutating history.

### Seller document evidence

| Object | Minimum contract |
|---|---|
| EVIDENCE.SELLER_DOCS_STAGE | Internal stage with directory enabled; contains only 2-3 tiny synthetic PDFs |
| EVIDENCE.DOCUMENTS | document_id, seller_id, product_id, stage_path, filename, sha256, version, parsed_at |
| EVIDENCE.DOCUMENT_CHUNKS | chunk_id, document_id, page_number, section_path, chunk_text, chunk_hash |
| EVIDENCE.SELLER_CLAIM_BINDINGS | claim_id, product_id, claim_key, operator, typed_value, chunk_id, binding_status, reviewer, binding_hash |
| EVIDENCE.V_SEARCHABLE_SELLER_CHUNKS | Search projection with seller_id, product_id, document_id, page_number, chunk_id, and text |
| Cortex Search service EVIDENCE.SELLER_EVIDENCE_SEARCH | Index only the seller chunk view; filter attributes seller_id/product_id/document_id/page_number; TARGET_LAG=1 day; serving AUTO_SUSPEND=1800 seconds |

AI_PARSE_DOCUMENT is the parsing function, not a persisted object. The reproducible ingestion worksheet uploads one PDF, calls it in LAYOUT mode with page splitting, normalizes the result into DOCUMENT_CHUNKS, and records the document hash. No task or recurring refresh is needed.

SELLER_CLAIM_BINDINGS is the trust boundary: the evaluator consumes a typed limitation only when it points to an exact parsed chunk. Search finds the passage; it does not manufacture a claim. For P0, one reviewed synthetic binding is enough.

### Decision execution and audit

| Object | Minimum contract |
|---|---|
| Stage DECISION.CODE_STAGE | Versioned evaluator package and pinned dependencies used by the Snowpark procedure |
| DECISION.REQUESTS | request_id, company_id, mission_id, context_version, created_by, created_at, idempotency_key |
| DECISION.INPUT_SNAPSHOTS | snapshot_id, request_id, source_bundle VARIANT, fact_ids ARRAY, claim_ids ARRAY, chunk_ids ARRAY, input_hash, created_at |
| DECISION.RUNS | run_id, request_id, snapshot_id, evaluator_version, git_sha, input_hash, decision_hash, selected_product_id, status, reason_codes ARRAY, counterfactual VARIANT, output VARIANT, query_id, created_at |
| DECISION.CITATIONS | citation_id, run_id, citation_type, fact_id, document_id, chunk_id, page_number, exact_excerpt, source_hash |
| DECISION.APPROVAL_LEDGER | event_id, decision_hash, actor_id, actor_role, action, occurred_at, previous_event_hash, event_hash |
| DECISION.V_AUDIT_TRAIL | Read projection joining request, snapshot, run, citations, and approval events |
| Procedure DECISION.RUN_SIRA_DECISION(request_id VARCHAR) | Owner-rights Snowpark Python procedure; idempotently loads the frozen snapshot, calls the existing deterministic evaluator, and writes/returns the authoritative result |

Every run records evaluator version, repository git SHA, Snowflake query ID, input hash, decision hash, fact IDs, claim/chunk IDs, and counterfactual. The approval table is application-append-only by grant and hash-chained; do not call it cryptographically immutable.

### Account capability gate before building

CoCo must verify these against the actual account:

1. Account cloud, region, and edition.
2. Whether this is a dedicated CoCo/hackathon trial. Ordinary Snowflake trials explicitly do not support Cortex Code CLI.
3. CORTEX_ENABLED_CROSS_REGION and an allowed Cortex model. AI_PARSE_DOCUMENT is not native in AWS Mumbai/Azure Pune and may require cross-region inference.
4. SIRA_SF_BUILD_ROLE can create stage, procedure, Cortex Search service, and use SNOWFLAKE.CORTEX_USER.
5. Python runtime availability and whether rfc8785 is present in INFORMATION_SCHEMA.PACKAGES. The existing domain hash implementation imports it at python/domain/hashing.py:21.
6. Remaining daily Cortex allowance and trial balance.

If CoCo cannot run, stop and obtain the dedicated CoCo-enabled account; Codex is not a substitute for this hackathon requirement.

### Verified feature availability and trial conclusion

The documentation-level result below is verified; live availability is still an account preflight because region, role grants, model access, and the hackathon's account type are unknown.

| Capability | Official status and constraints | Trial/account conclusion | P0 decision |
|---|---|---|---|
| Cortex Search | Generally available in supported regions. Creation needs service/schema/database privileges, source SELECT, warehouse USAGE, and a Cortex role. Search runs with owner rights, so it must never index private buyer facts. | Not listed as an ordinary-trial exclusion; creation/query still depend on region, RBAC, and embedding-model access. | Use if the live preflight passes; otherwise use filtered chunk SQL. |
| Cortex Agents | Generally available; can use Search, Analyst, and scalar stored-procedure/UDF custom tools. Caller default-role permissions and model access matter, and generated answers/citations are not guaranteed authority. | Not listed as a trial exclusion, but live model, role, REST, and cross-region access are account-specific. | P1 only. |
| Cortex Analyst | Available through semantic views and as an Agent tool; requires supported models and semantic-view/table privileges. | No ordinary-trial exclusion found; supported model access must be checked in the account. | P1 only; direct SQL is sufficient for P0. |
| Snowpark Python | Standard Snowflake capability; documented Python runtimes include 3.10-3.14. A regular X-Small warehouse is sufficient for this evaluator. | No trial exclusion. Individual dependency availability must be checked in INFORMATION_SCHEMA.PACKAGES. | Required P0. |
| Streamlit in Snowflake | Generally available with warehouse and container runtimes; container runtime introduces compute-pool/account requirements, while warehouse runtime cannot call Cortex Agent APIs. | Not explicitly excluded from trials, but runtime/account capability is specific to the live account. | P1 only. |
| AI_PARSE_DOCUMENT | Native only in selected regions and supports cross-region inference elsewhere; it requires a staged file and SNOWFLAKE.CORTEX_USER. Current native-region documentation does not include AWS Mumbai/Azure Pune. | Not listed as a trial exclusion. An ordinary no-payment trial may be capped at roughly 10 Cortex AI credits/day. | Required P0 if cross-region is available; documented Snowpark parsing fallback otherwise. |
| CoCo / Cortex Code CLI | Generally available for eligible commercial accounts with a supported model and cross-region inference. Windows native use is supported. | **Ordinary Snowflake trial accounts explicitly do not support it.** A dedicated Cortex Code trial or hackathon-provided eligible account is mandatory. | Hard gate before any build. |

## 4. Exact repository files to keep, modify, or add

### Preserve unchanged in P0

| Path | Why |
|---|---|
| python/domain/** | Existing validation and canonical hashing contract |
| python/decision_engine/graph_v1.py | Deterministic authority, including company-context counterfactual |
| python/decision_engine/graph_v1_models.py | Typed graph input/output contract and provenance |
| python/decision_engine/graph_v1_recall.py | Existing bounded recall logic |
| python/decision_engine/bounds.py | Exact numeric bounds |
| python/decision_engine/ranking.py | Existing ranking |
| python/decision_engine/graph_v1_fixtures.py | Keep its compiler-compatible fixed scenario for today; map Snowflake data into its DecisionSourceBundle contract |
| services/api/sira_api/graph_ledger.py | Existing deterministic ledger projection |
| services/api/sira_api/identity.py | Existing Firebase/guest tenant isolation |
| python/persistence/database.py and mission_repository.py | PostgreSQL remains mission persistence |
| apps/web/components/auth/** | Existing login and guest fallback |
| Existing evaluator unit/property tests | Regression oracle |

### Modify minimally

| Path | Change |
|---|---|
| pyproject.toml and uv.lock | Add a pinned optional/runtime Snowflake connector and Snowpark dependency set |
| .env.example | Add names only for account, user/authenticator, role, warehouse, database, and enable flag; never commit secrets |
| services/api/sira_api/config.py | Typed, fail-closed Snowflake settings |
| services/api/sira_api/main.py | Construct and close one Snowflake integration service |
| services/api/sira_api/dependencies.py | Inject the integration into workspace/workflow services |
| services/api/sira_api/service.py | Add a provider-compiled DecisionSourceBundle path and split generic graph/ledger evaluation from fixture-only naming |
| services/api/sira_api/workspace_service.py | Invoke the Snowflake decision path for the fixed demo and emit existing artifact/proposal structures |
| services/api/sira_api/workspace_schemas.py | Add typed citation and Snowflake run/audit references only if the existing open artifact payload cannot carry them |
| services/api/sira_api/workspace_routes.py | Add the minimum decision citation/approval read or confirm endpoint |
| python/agents/sira_agents/commerce_tools.py | Add an allowlisted “evaluate cited decision” tool; it calls the service and never ranks locally |
| contracts/openapi/openapi.json | Regenerate only if routes/types change |
| packages/api-client/src/client.ts and types.ts | Regenerate only if contract changes |
| apps/web/components/workspace/commerce-workspace.tsx | Reuse the existing information action and third panel for causal diff, citations, run ID, and approval |
| apps/web/components/workspace/commerce-workspace.module.css | Only the minimal cited-decision artifact styling |
| compose.yaml | Pass Snowflake setting names only if Docker is used for the final demo |

Do not overwrite the current dirty work. Before implementation, record and commit the existing pre-Snowflake patch on the intended branch. Current branch is Ui at 345bd22 while origin's default branch is core-backend, and the dirty files overlap the Snowflake seams.

### Add

| Path | Purpose |
|---|---|
| infra/snowflake/00_preflight.sql | Account, region, role, package, feature, and cost gate |
| infra/snowflake/01_bootstrap.sql | Roles, X-Small warehouse, monitor, database, schemas, grants |
| infra/snowflake/02_governed_tables.sql | Governed structured tables and current-context view |
| infra/snowflake/03_evidence_pipeline.sql | Stages, document/chunk/binding tables, parse normalization |
| infra/snowflake/04_cortex_search.sql | Search service and filterable projection |
| infra/snowflake/05_decision_ledger.sql | Requests, snapshots, runs, citations, approval ledger, audit view |
| infra/snowflake/06_snowpark_evaluator.sql | Procedure registration and versioned code-stage references |
| infra/snowflake/07_seed_demo.sql | Tiny fixed products, offers, two buyer-context versions, and seller bindings |
| infra/snowflake/worksheets/causal_proof.sql | One-page executed proof of before/after decisions, citations, and approvals |
| python/integrations/snowflake/__init__.py | Integration package |
| python/integrations/snowflake/models.py | Typed transport models |
| python/integrations/snowflake/client.py | Parameterized Snowflake query boundary, timeouts, query IDs |
| python/integrations/snowflake/source_mapper.py | Snowflake rows to DecisionSourceBundle |
| python/integrations/snowflake/decision_service.py | Idempotent request/search/snapshot/procedure/approval orchestration |
| python/integrations/snowflake/snowpark_handler.py | Thin procedure entrypoint importing the existing evaluator |
| scripts/snowflake_smoke.py | One bounded account and causal-path smoke command |
| fixtures/snowflake/buyer_context.json | Two versioned buyer contexts differing in one private fact |
| fixtures/snowflake/seller_evidence/product-a-hubspot-limitation.pdf | Tiny synthetic seller-controlled evidence document |
| fixtures/snowflake/seller_evidence/product-b-hubspot-support.pdf | Tiny comparison evidence document |
| tests/unit/test_snowflake_source_mapper.py | Mapping and source-provenance parity |
| tests/integration/test_snowflake_decision_path.py | Opt-in live Snowflake causal and audit proof |
| docs/COCO_BUILD_LOG.md | Sanitized prompt/session/object/query-ID evidence |

No new frontend application or page should be added. The existing artifact panel already supports source references and the requested on-demand detail interaction.

## 5. P0 tasks for today

Total engineering estimate: 6.5-8 hours. Expected wall-clock time can be 5.5-7 hours if the fixture/document lane and Snowpark packaging lane overlap after the object contract is fixed.

| Order | Dependency | Task and completion criterion | Owner/tool | Estimate |
|---:|---|---|---|---:|
| 0 | None | **Protect submission viability.** Confirm portal acceptance, save the draft entry, capture deadline state. Run CoCo version/login/account preflight. Stop if the account is an ordinary non-CoCo trial. | Human + CoCo | 0.3 h |
| 1 | 0 | **Freeze baseline.** Capture current dirty diff, select the intended branch, and commit the pre-Snowflake work without rewriting it. Record HEAD 345bd22 as the committed audit baseline. | Codex/human | 0.3 h |
| 2 | 0 | **Lock object contract and cost guardrails.** CoCo authors and executes bootstrap, schemas, grants, X-Small warehouse, monitor, and preflight evidence. | CoCo | 0.6 h |
| 3 | 2 | **Seed the causal fixture.** Two context versions, two products/offers, and two one-page synthetic seller PDFs; one fact differs. List dataset provenance as team-authored synthetic data. | CoCo + Codex review | 0.4 h |
| 4 | 2,3 | **Build evidence path.** Upload, parse with AI_PARSE_DOCUMENT, normalize page-aware chunks, bind one typed limitation to an exact chunk, create/query Search, capture query IDs. | CoCo | 0.8 h |
| 5 | 2,3 | **Run evaluator in Snowpark.** Package the existing pure modules, implement the thin request-id procedure, write frozen snapshots/runs, and prove parity with the local expected winner/hash. | CoCo + Codex review | 1.4 h |
| 6 | 4,5 | **Complete audit path.** Add citations, approval grant boundary/hash chain, audit view, and execute the before/after causal worksheet. | CoCo | 0.6 h |
| 7 | 5,6 | **Wire FastAPI.** Add the integration client/mapper/service, parameter binding, idempotency, timeouts, and explicit failure responses. Mirror the Snowflake run into the existing mission artifact, not a second decision authority. | Codex | 1.1 h |
| 8 | 7 | **Reuse the product UI.** Render the selected option, causal reason, exact seller excerpt/page, Snowflake run ID, and human approval in the existing third panel. No new screen. | Codex | 0.6 h |
| 9 | 4-8 | **Run one narrow verification pass.** Existing evaluator regression, mapper unit test, live Snowflake causal smoke, UI click-through, ledger query. Fix only demo blockers. | CoCo + Codex | 0.8 h |
| 10 | 9 | **Capture and submit.** Record the three-minute path, screenshots, CoCo evidence, executed Worksheet, architecture diagram, frozen commit, deck, dataset/license disclosure, and portal receipt. | Human + Codex | 0.8 h |

### Hard decision gates

- At +30 minutes: if CoCo cannot access the account, stop engineering and obtain the hackathon/dedicated CoCo trial.
- At +2 hours: if AI_PARSE_DOCUMENT needs unavailable cross-region access, keep the private-fact causal proof mandatory and use Snowpark PDF/text parsing only as the documented fallback.
- At +3 hours: if Cortex Search cannot be created, switch to exact filtered chunk retrieval in Snowflake SQL.
- At +4 hours: if Snowpark packaging fails on rfc8785, vendor the small pinned dependency into CODE_STAGE or isolate canonical hashing at the procedure boundary; do not rewrite ranking semantics.
- Once the complete causal flow works, freeze it. Do not add Cortex Agent, Streamlit, Prava, Temporal, or a second category.

## 6. P1 improvements only after the demo works

Ordered, and explicitly contingent on a green P0:

1. Add SIRA_DECISION_AGENT as a non-authoritative explanation lane using seller Search and RUN_SIRA_DECISION as a custom tool. FastAPI still binds its prose to authoritative run/citation rows.
2. Add a commerce semantic view and Cortex Analyst for exploratory structured questions. Direct SQL remains the deterministic runtime path.
3. Add a minimal Streamlit audit console only to earn extra consideration and help judges inspect runs; do not replace the product UI.
4. Add role-based access policies, masking, tags, and retention policies for production-grade buyer/seller isolation.
5. Generalize source mapping beyond the fixed four-product fixture and remove ConsultCo-specific compiler assumptions.
6. Add seller document review/version workflows and claim supersession.
7. Add evaluation telemetry, cost dashboards, and automated service suspension.
8. Add more categories and adversarial evidence cases only after the meeting-intelligence path remains deterministic.

## 7. Test plan and three-minute demo

### Minimal test matrix

| Test | Assertion | Proof |
|---|---|---|
| Existing evaluator regression | Company-aware fixture still chooses the expected winner; generic run chooses the cheaper alternative | Existing tests/unit/test_decision_input_compiler.py:37-51 |
| Source mapper unit | Same Snowflake rows always create the same DecisionSourceBundle and input hash | New unit test |
| Missing evidence safety | Removed claim binding yields UNKNOWN/INSUFFICIENT_EVIDENCE, not a pass | Existing evaluator assertion plus mapper test |
| Snowpark parity | Local and Snowpark runs for the frozen snapshot agree on selected product, statuses, reason codes, and decision hash | Opt-in integration test and Worksheet |
| Document citation | Search result and DECISION.CITATIONS point to the same document, page, chunk hash, and exact excerpt | Live integration test |
| Causal materiality | Context v1 with HubSpot-required selects B; v2 without that one fact selects A; input and decision hashes differ | Live integration test and UI artifact |
| Idempotency | Reusing one request/idempotency key returns the existing run rather than duplicating it | Live integration test |
| Approval binding | Approval references the exact decision hash and app role cannot update/delete it | Permission check and audit query |
| Tenant/privacy boundary | Another organization cannot request the buyer snapshot; seller search contains no buyer facts | API authorization check and Search projection inspection |
| Failure behavior | Search/procedure timeout produces a truthful unavailable state; no fabricated recommendation or approval is written | Targeted API test |

Do not run all 280 repository tests today. Run only the existing evaluator files touched by the integration contract, the new mapper unit test, the one live Snowflake integration test, and the visible UI flow.

### Three-minute demo script

| Time | Action | Visible proof |
|---:|---|---|
| 0:00-0:20 | State the problem and open the existing SIRA workspace | “Private buyer context + honest seller evidence -> cited decision” |
| 0:20-0:45 | Ask SIRA for meeting intelligence for 10 seats, $100/seat/month, HubSpot | Existing agentic chat captures a concise purchase mission |
| 0:45-1:10 | Open the recommendation information action | Third panel shows Product A's parsed seller limitation with document name, exact excerpt, page/chunk hash |
| 1:10-1:35 | Run with private company context v1 | Product A becomes PASS/ineligible; Product B wins; reason code points to HubSpot/budget conflict |
| 1:35-2:00 | Run the counterfactual context v2 with only CRM_SYNC_REQUIRED removed | Product A wins; side-by-side hashes and changed fact are visible |
| 2:00-2:25 | Approve one decision | Approval event displays actor, timestamp, event ID, and exact decision hash; no payment is attempted |
| 2:25-2:50 | Open the executed Snowflake audit Worksheet/Snowsight result | Input snapshot, citations, two decision runs, approval event, Snowflake query IDs |
| 2:50-3:00 | Show CoCo build log/session evidence and close with the pitch | CoCo and Snowflake use are indisputable |

The presenter should never navigate to a standalone decision room, payment page, Prava screen, or Streamlit app during the primary demo.

## 8. Rubric scorecard and visible proof

The scores are targets, not a guarantee.

| Rubric | Target | What earns it | What the judge can see |
|---|---:|---|---|
| Technical Execution | **38/40** | AI_PARSE_DOCUMENT, page-aware chunks, Cortex Search, Snowpark execution of the existing evaluator, deterministic hashes/counterfactual, idempotency, citations, append-only approval grants, CoCo-authored/executed assets | Snowsight objects; parsed chunk; Search result; Snowpark query ID; before/after decision hash; audit query; CoCo session |
| Real-World Relevance | **29/30** | Buyers need private company fit, sellers need honest limitations/PASS, and enterprises need approval lineage; Snowflake separates governed buyer facts from seller evidence | One realistic 10-seat HubSpot/budget decision; exact seller limitation; private fact never exposed to seller Search |
| Solution Completeness | **28/30** | Existing professional UI, authenticated/guest isolation, end-to-end chat -> evidence -> deterministic decision -> explanation -> approval -> audit | One uninterrupted three-minute flow and reproducible setup/Worksheet |
| **Total** | **95/100** | Narrow and complete beats broad and fragile | Frozen demo commit, deck, repository, and live proof |

### Proof-to-objection map

| Likely objection | Required rebuttal |
|---|---|
| “Snowflake is only a database.” | One Snowflake private fact changes eligibility and the winner; Snowflake parses/retrieves the decisive document and runs the evaluator. |
| “The answer is hard-coded.” | Two immutable context versions differ by one fact and produce distinct live run/query/decision IDs. |
| “This is generic RAG.” | Retrieved evidence is converted only through a typed, cited binding; deterministic gates/ranking own the result. |
| “The LLM hallucinated the citation.” | UI citations come from DECISION.CITATIONS, not model text, and include chunk/page/hash. |
| “The agent approved its own action.” | Human confirmation writes a separate event bound to the decision hash. |
| “This is an old app with Snowflake bolted on.” | Dated pre-existing disclosure plus CoCo sessions, new Snowflake files, executed queries, and commits show the new decisive path. |
| “The prototype depends on fragile integrations.” | Primary path is Next.js + FastAPI + Snowflake only; Prava, Temporal, Senso, Agent, and Streamlit are absent from P0. |

### Submission proof checklist

- Portal still accepts the entry; confirmation screenshot/email saved
- Team profile, idea, selected challenge, and English deck complete
- Judge-accessible repository pinned to one submitted commit
- README setup, architecture diagram, data inventory, limitations, and demo commands
- Tiny synthetic PDFs and dataset provenance/licensing listed
- Cortex/CoCo version, sanitized session evidence, and Snowflake query IDs
- Executed causal Worksheet and Snowsight object screenshots
- Three-minute live path and backup recording if the portal allows it
- No credentials, private account identifiers, or confidential source documents committed

## 9. CoCo CLI execution and evidence plan

Official rules require CoCo/Cortex Code CLI. It must do material work; a screenshot of installation is not sufficient.

### CoCo must genuinely build and test

1. Inspect the repository and identify DecisionSourceBundle, evaluate_decision_graph, and the hash dependency seam.
2. Author or materially revise infra/snowflake/00-07 SQL assets.
3. Execute account preflight and bootstrap against the real Snowflake account.
4. Create and populate the stage, document/chunk tables, Search service, governed tables, and ledger.
5. Upload and run the one-page AI_PARSE_DOCUMENT smoke test.
6. Query Cortex Search and show the returned document/chunk/page IDs.
7. Package/refine the Snowpark handler around the existing evaluator.
8. Run both context versions and validate the counterfactual winner change.
9. Insert and query the approval event plus joined audit view.
10. Diagnose at least one real build/runtime issue, apply the correction, and rerun the validation.

Codex may review contracts, integrate FastAPI/UI, and fix application glue. Codex must not be the sole author of the Snowflake DDL, Snowpark wrapper, or real-account validation.

### Evidence to retain

- cortex --version and sanitized Snowflake connection/account evidence
- CoCo session IDs and conversation files under the local Snowflake Cortex conversations directory
- Timestamped, sanitized terminal transcript or short recording
- Git commits/diff identifying CoCo-authored Snowflake assets
- docs/COCO_BUILD_LOG.md mapping prompt -> file/object -> Snowflake query ID -> result
- Executed causal Worksheet and Snowsight object screenshots
- Final end-to-end query IDs and submitted commit SHA

Never record passwords, private keys, connection TOML contents, tokens, or full account identifiers. Redact them before screenshots.

## 10. Cost controls for the USD 400 trial

Goal: spend less than 10 percent of the trial during building and preserve the rest for retries/final judging.

- Use only SIRA_HACK_XS_WH: Gen1 Standard X-Small, one cluster, one-credit/hour rate, 60-second minimum per resume.
- AUTO_SUSPEND=60 seconds and AUTO_RESUME=true. Never leave a worksheet query running.
- Attach the 10-credit warehouse monitor. It controls warehouse compute only, not Cortex/serverless use.
- Keep data to two context versions, two products, two offers, 2-3 one-page PDFs, fewer than 30 chunks, and fewer than 30 Search/LLM calls.
- Use AI_PARSE_DOCUMENT LAYOUT mode once per hashed document. Skip unchanged hashes.
- Use one Cortex Search service with TARGET_LAG=1 day; manually suspend it between work blocks. The automatic serving-suspend floor is materially longer than the warehouse's.
- Do not create tasks, dynamic tables, compute pools, Snowpark-optimized warehouses, multi-cluster warehouses, Streamlit containers, Cortex Agent, or Analyst in P0.
- Set statement timeouts in the connector and cancel failed work promptly.
- Check warehouse metering and Cortex/serverless usage after each build phase. Stop at an unexpected 2-credit delta and diagnose before continuing.
- Ordinary no-payment trial accounts may have an approximate 10 Cortex AI credits/day limit; the actual hackathon account must be checked.
- Credit-to-USD conversion varies by contract/region. Use credits as the enforcement unit, not a guessed dollar conversion.

Expected prototype consumption is small: a few warehouse credits, a few PDF pages, a tiny Search index, and fewer than 30 retrieval calls. The cost risk is idle Search/serverless activity, not the dataset.

## 11. Pre-existing-versus-hackathon-work disclosure

The public rules require originality/licensing but do not explicitly ban pre-existing work. Be precise rather than implying the whole repository was created for this submission.

### Verifiable pre-Snowflake baseline

The repository history begins 2 August 2026. Current audited baseline is branch Ui at commit 345bd22. Representative existing commits:

- 839ef96 — deterministic decision engine
- 24c7202 — backend flow
- 770026a — demo readiness ledger
- 68b14b4 — persisted decision inputs
- 1e3f62f — persistent agent runtime
- 71c0a26 — Firebase auth/workspace flow
- 345bd22 — current committed baseline

Disclose as pre-existing before this Snowflake integration:

- SIRA + SEIL concept and interface
- Next.js/FastAPI application
- deterministic Python evaluator, fixtures, tests, and hashes
- PostgreSQL persistence and approval model
- OpenAI agent runtime, Firebase identity, and prior provider integrations

Disclose as built for this Snowflake submission only after it actually exists:

- Snowflake roles, warehouse, database, schemas, stages, and governed tables
- AI_PARSE_DOCUMENT and Cortex Search evidence pipeline
- Snowpark evaluator wrapper/execution
- Snowflake source mapper and FastAPI orchestration seam
- cited decision and Snowflake approval ledger
- causal two-context demo fixture and executed Worksheet
- CoCo-authored/tested artifacts and build log
- hackathon-specific documentation and deck

Third-party disclosure:

- List every non-Snowflake dataset, source URL, and license.
- Label the demo company, products, prices, and PDFs as fictional/team-authored synthetic data.
- List library/API licenses and contributions by registered participant.
- Do not claim production customers, verified live provider execution, or that all pre-existing code was written during the hackathon.

## 12. Top blockers and fallback architecture

### Blocker register

| Priority | Blocker | Detection | Mitigation / owner |
|---:|---|---|---|
| 1 | Ordinary Snowflake trial cannot use CoCo CLI | cortex login/version/account preflight fails or docs identify ordinary trial | Obtain dedicated Cortex Code/hackathon trial immediately; contact event support. No technical substitute satisfies the requirement. |
| 2 | Submission deadline conflict/closed portal | Portal does not accept draft/final entry | Capture screen/time, email support+cococlihack@hack2skill.com, preserve complete submission bundle and receipt trail. |
| 3 | India-region AI_PARSE_DOCUMENT needs cross-region | One-page parse smoke fails due model/region | Enable CORTEX_ENABLED_CROSS_REGION with authorized role; otherwise use the fallback below and make the private fact the mandatory causal proof. |
| 4 | Cortex Search/RBAC/model unavailable | Search create/query preflight fails | Use exact filtered retrieval from parsed chunk rows; keep document/page/chunk citations. |
| 5 | Snowpark package incompatibility, especially rfc8785 | Package lookup or procedure import fails | Vendor the pinned small dependency into CODE_STAGE or isolate canonical hashing at the procedure boundary; never rewrite evaluator semantics under deadline. |
| 6 | Fixture coupling in compiler/service | Snowflake source cannot compile without ConsultCo assumptions | Keep the fixed scenario and map Snowflake rows to the existing fixture-compatible IDs; generalization is P1. |
| 7 | Dirty files and branch ambiguity | Current Ui worktree overlaps API/UI seams; origin default is core-backend | Commit the complete current patch as the pre-Snowflake baseline on the selected branch before implementation; never reset or overwrite it. |
| 8 | Live runtime still uses fixture mode | /health reports fixture_mode=true | Set API mode only after Snowflake smoke passes; keep a separate recovery URL/commit. |

### Fallback architecture

**Fallback F: SQL-first Snowflake evidence plane**

Use the same Next.js/FastAPI interface, governed facts, internal document stage, AI_PARSE_DOCUMENT output, Snowpark evaluator, citations, and approval ledger. Replace Cortex Search with a deterministic, product-filtered SQL query over DOCUMENT_CHUNKS using exact phrases/metadata. Use reason-code templates for the cited explanation. No Cortex Agent, Analyst, or Streamlit.

This fallback still satisfies the non-negotiable proof:

- a private Snowflake fact changes the winner;
- a seller document is processed inside Snowflake;
- the evaluator runs in Snowpark;
- the explanation cites an exact parsed page/chunk;
- approval is bound to the Snowflake decision hash.

It loses some Search-specific technical points but protects a complete, honest demo. If AI_PARSE_DOCUMENT itself is unavailable, stage the PDF and parse it in Snowpark only as a documented fallback; the private governed fact must remain the demonstrated material decision change.

### Verified official references

Verified on 6 August 2026:

- [Hack2Skill event page](https://hack2skill.com/event/cococlihack/)
- [YourStory CoCo CLI microsite](https://coco-cli.yourstory.com/)
- [Linked Official Rules](https://docs.google.com/document/d/e/2PACX-1vQ0RB2XJB3MuE_dZbroHkqlicLD2O_Y3FaGgj03JwkC6_dhUfRqi4az-Teb62S43km27dg9YlMarOD6/pub)
- [Cortex Code CLI](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code-cli)
- [Snowflake trial account limits](https://docs.snowflake.com/en/user-guide/admin-trial-account)
- [Cortex Search overview](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-overview)
- [Cortex Search costs](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-costs)
- [Cortex Agents](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents)
- [Cortex Agent custom tools](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-manage)
- [Cortex Analyst](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst)
- [AI_PARSE_DOCUMENT](https://docs.snowflake.com/en/user-guide/snowflake-cortex/parse-document)
- [Snowpark Python](https://docs.snowflake.com/en/developer-guide/snowpark/python/index)
- [Snowflake Streamlit privileges](https://docs.snowflake.com/en/developer-guide/streamlit/object-management/privileges)
- [Cross-region inference](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cross-region-inference)
- [Warehouse consumption](https://docs.snowflake.com/en/user-guide/warehouses-overview)

## GSTACK REVIEW REPORT

| Review | Runs | Status | Decisive finding |
|---|---:|---|---|
| CEO | 2 | DONE WITH CONCERNS | The causal proof is live (v1 NoteSync, v2 MeetAI, cited hashes), but the implementation honestly uses the SQL-first fallback rather than claiming Cortex Agent/Analyst orchestration. |
| Design | 2 | CLEAR | Chat remains primary; cited decision, counterfactual, evidence, run/hash, and explicit non-purchasing approval live in the on-demand third panel. |
| Engineering | 2 | DONE WITH CONCERNS | Tenant-scoped request/read/approval code, parser-derived chunks, post-create grants, scoped audit joins, explicit 503 handling, and focused regressions are present. The target account still needs the forward migration. |
| Developer experience | 2 | DONE WITH CONCERNS | Ordered SQL docs and `scripts/apply_snowflake.ps1` now cover bootstrap/upload/bundle/proof. CoCo session evidence is logged, but sanitized screenshots/query IDs remain submission packaging work. |

### Final implementation verification (6 August 2026)

- Integrated `origin/core-backend` into `snowflake-hackathon` before final review.
- Focused tests: 5 passed (decision causality, tenant isolation, Prava MCP regression).
- Web TypeScript, focused Ruff, OpenAPI/client drift, PowerShell parsing, and diff checks pass.
- Live target proof already shows the material winner change and citations. The original decisive chunks and approval row predate the final lineage/tenant corrections.
- Snowflake reports the same account as organization/account `ERJAVEX-TG61158` and locator `AN78325`. Final verification confirmed all request/approval scope columns and 2/2 parser-derived decisive chunk hashes in that account.
- Cortex Search exists in the original live build but is not the runtime authority path. Snowpark plus governed SQL and deterministic reason templates are the submitted fallback architecture.
- A recursive Codex reviewer could not run because the installed CLI is too old for its configured model; sub-agent and primary-agent reviews supplied the final gates.

Final verdict: **CODE AND SNOWFLAKE SCHEMA COMPLETE.** The remaining release work is deployment configuration plus one deliberate UI approval smoke test; no account migration blocker remains.
