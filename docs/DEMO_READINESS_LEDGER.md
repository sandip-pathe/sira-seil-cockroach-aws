# Demo Readiness Ledger

Updated: 2026-08-02

Branch reviewed: `core-backend`

Implementation reviewed through: `7bdbad4` plus the current Senso-ingestion batch

This ledger reconciles the pre-P0 quality audit at `f4ac492` with the P0 fixes that followed it. It is the short, current checklist for the demo; the earlier audit remains useful background but its original P0 verdict is stale.

## Current verdict

- **GO:** an explicitly labelled, deterministic fixture demo of company-aware evaluation, seller PASS, eligible alternatives, ranking, counterfactual, ledger, and proposed Stackfile patch.
- **CONDITIONAL GO:** the laptop-backed API demo after the PostgreSQL checks and one complete startup smoke test below pass.
- **NO-GO:** claims that arbitrary company intent, Senso retrieval, autonomous agents, or a real Prava/merchant purchase work end to end.
- **NO-GO:** production or real-money use.

## Verified and closed

| ID | Result | Evidence |
|---|---|---|
| CORE-01 | **PASS:** The decision engine is deterministic and uses hard eligibility gates before bounded preference/TCO ordering. Missing, stale, or conflicting evidence cannot silently become a pass. | Decision and property suites; frozen demo ledger and hashes. |
| CORE-02 | **PASS:** The demo proves `SIRA_INELIGIBLE`, seller `SEIL_PASS`, eligible runner-up/winner, company-aware winner change, and a proposed Stackfile patch. Seller positioning is excluded from rank. | `tests/unit/test_decision_graph_v1.py`; `tests/unit/test_domain_decision.py`. |
| CORE-03 | **FIXED:** Strict typed comparisons, exact evidence scope, comparable currency/horizon, assessed-evidence risk rules, and coherent deduplication are enforced. | `a1f22bb`. |
| DEMO-01 | **FIXED:** Arbitrary request text can be saved only as an explicitly unevaluated draft. Discovery requires the declared `consultco_meeting_intelligence_v1` scenario, and every request/decision projection carries the non-production fixture mode and label. | Primary and compatibility API tests; frozen Decision View and generated client contracts. |
| CORE-04 | **FIXED FOR THE DEMO:** Replay, simulation, and counterfactual execution resolve the canonical persisted Evaluation Run and verify its input hash, versions, evaluation time, frozen artifact hashes, evaluation hash, and aggregate bindings. If the exact fixture source no longer matches, the operation fails with `REPLAY_INPUT_UNAVAILABLE` instead of substituting current data. | Replay-fidelity unit tests and the combined counterfactual/simulation/replay API regression. |
| CORE-05 | **FOUNDATION COMPLETE:** The deterministic engine now compiles from a complete credential-free `DecisionSourceBundle`, not a filesystem-only loader. Accepted Buyer Passport, Purchase/Requirement Brief, Stackfile, Pack, evidence, offer, contract, usage, taxonomy, and normalization documents are stored as one immutable tenant-scoped source snapshot; discovery, calibration, and accepted rule changes use that exact hash-bound snapshot. The demo snapshot remains explicitly `DEVELOPMENT_FIXTURE`; Senso composition is tracked in CORE-09. | Compiler divergence tests, source-snapshot repository tests, API discovery/calibration regressions, and migration `a4c8e1f7b205`. |
| CORE-06 | **FIXED:** Buyer facts carry actor role and authority. A unique higher-authority assertion wins deterministically; equal-authority disagreement stops compilation unless the Purchase Brief's declared field owner records an explicit selection and reason. The winner, losing fact IDs, roles, strategy, and rationale are frozen into evaluation hashes and the Decision Ledger. | Actor-conflict compiler, hash, gate-lineage, authorization, and ledger tests. |
| CORE-07 | **FIXED FOR DECLARED REQUIRED COMPONENTS:** Pack candidates can declare required products. Plan construction resolves transitive dependencies in stable dependency-first order, blocks missing/ambiguous/cyclic closure, applies hard gates to every component, aggregates preferences with versioned exact operators, and sums bounded TCO and fee lines across the bundle. Broad combinatorial optimization and multi-merchant execution remain deferred. | Two-component ordering/TCO/aggregation tests, weakest-link policy test, and missing/cycle failure tests. |
| CORE-08 | **FIXED:** Recall applies a frozen category/JTBD/region/Pack-status policy before deduplication. Included, deduplicated, and excluded records now have exact counts; exclusions retain stable reason codes in persistence and the Decision Ledger instead of being reported as zero. | Recall coverage, duplicate merge, revoked Pack, ledger, API, and persistence tests. |
| CORE-09 | **COMPOSITION COMPLETE IN CODE:** Folder-scoped Senso search resolves exact content versions before model use. Agent output is a strict advisory fact proposal with zero rank/authority fields; support must be an exact document span. Only an authorized human acceptance creates a Buyer Passport fact. Provider/content/version/chunk/time/evidence hash and production-versus-fixture mode survive into the frozen fact hash. A live credentialed run is still required. | Senso ingestion, unversioned-source rejection, hallucinated-span rejection, authority-boundary, fixture-label, compiler-provenance, agent-runtime, and REST-adapter tests. |
| PAY-01 | **FIXED:** Approval expiry is rechecked at hosted-session creation, browser return, and final dispatch; stale authority becomes `EXPIRED` before side effects. | `47db419`. |
| PAY-02 | **FIXED:** Provider uncertainty and hosted-session failures are recoverable; malformed outbox events no longer starve later work. | `70dc0a3`. |
| PAY-03 | **FIXED:** Fulfillment retries separately from checkout, so paid-but-unfulfilled recovery does not repeat the charge. | `d6ee047`. |
| PAY-04 | **FIXED IN CODE:** Concurrent first idempotency claims use a savepoint, resolve the uniqueness race, and reread the canonical record. Live PostgreSQL proof is still open below. | `86ef60a`. |
| PAY-05 | **FIXED IN CODE:** Purchase Intent merchant, Pack, offer, quote, amount, currency, line items, fulfillment expectations, and Stackfile patch now come from a hashed snapshot on the exact persisted selected plan. Missing or altered terms fail closed. | Batch 1 transaction-binding tests; live PostgreSQL proof remains open. |
| PAY-06 | **PASS IN CONTRACT:** Prava binds the exact ISO currency at session creation and the same canonical currency reaches the controlled merchant. The official payment-result response does not return a currency field, so result-time currency comparison is not possible; session/order/amount/merchant checks prevent substitution. | Prava adapter contract tests and official [Create Session](https://docs.prava.space/api-reference/create-session)/[Get Payment Result](https://docs.prava.space/api-reference/get-payment-result) documentation. |
| PAY-07 | **FIXED IN APPLICATION:** An authorized approver can revoke the exact intent hash before merchant dispatch. Revocation invalidates local hosted-session/browser authority, retires queued checkout work, and the worker recheck proves zero Prava or merchant dispatch. | Approval API/domain/worker tests; provider-side session cancellation remains open under LIVE-03. |
| SEC-01 | **PASS IN CODE:** Production defaults fail closed, fixture adapters are labelled, tenant scoping/RLS policies exist, and the one-time Prava credential stays out of persistence, payloads, workflow history, and errors. | Production-boundary, provider, worker, and contract tests. |

## Required on the laptop for the demo

| ID | Priority | Required proof | Done when |
|---|---:|---|---|
| DB-01 | P0 | **Run fresh PostgreSQL migrations with separate owner and runtime roles.** PostgreSQL is canonical; SQLite is not an acceptable substitute. | Alembic reaches head; runtime is `NOSUPERUSER`, `NOBYPASSRLS`, non-owner; forced RLS allows same-tenant access and denies cross-tenant access. |
| DB-02 | P0 | **Run the idempotency race against live PostgreSQL.** The code fix is tested with mocks but database transaction behavior has not been certified locally. | Two concurrent first requests produce one canonical idempotency record and no 500/duplicate intent. |
| DEMO-02 | P0 | **Complete one laptop startup smoke test.** | Fresh setup starts web/API/worker, health reports the expected mode, migrations are current, and the chosen scripted path survives a refresh without changing hashes/state. |
| UI-01 | P0, UI owner | **Wire or deliberately scope the visible journey.** | The user can complete the claimed demo path; unavailable provider actions remain disabled and honestly labelled rather than reporting fake success. |

Docker is not required for these checks. A local laptop PostgreSQL/Temporal setup or reachable services on the laptop can be used.

## Required only if the demo claims live sandbox purchasing

| ID | Blocker |
|---|---|
| LIVE-03 | Compose Prava's official [Revoke Session](https://docs.prava.space/api-reference/revoke-session) operation for an already-created hosted session and certify it in sandbox. Application authority revocation already blocks merchant dispatch. |
| LIVE-04 | Configure authentic Prava, controlled merchant/entitlement, Temporal, and HTTPS return URL values and run the real sandbox contracts. Development adapters must remain visibly non-production. |
| LIVE-05 | Prove pending/timeout, unknown result, duplicate attempt, crash-after-charge, and paid-but-unfulfilled recovery against the sandbox without a duplicate charge. |
| LIVE-06 | Configure a real folder-scoped Senso key and OpenAI model, then run the composed ingestion path through human acceptance and a fresh Purchase Brief/source snapshot before claiming live company evidence affected a decision. The code seam is covered by CORE-09; no credentialed run has occurred. |

Until those pass, demonstrate the deterministic transaction state machine with labelled fixtures only; do not describe it as a completed purchase.

## Important checks and known misses

| Check | Current evidence |
|---|---|
| Focused P0 regression | **PASS:** 133 tests. |
| Approval-revocation regression | **PASS:** 37 focused API, domain, and worker tests; frozen OpenAPI and generated client checks pass. |
| Persistence-focused run | **PASS:** 73 tests; **2 skipped** because `SIRA_TEST_DATABASE_ADMIN_URL` was not set to a dedicated `sira_test` PostgreSQL database. |
| Python lint | **PASS:** Ruff. |
| Python typing | **PASS:** strict mypy across 23 source files. |
| Credential scan | **PARTIAL:** current-tree scan produced no listed credential finding; history mode is not green because its heuristic flags old hashes/example values. Baseline or narrow the history rules before treating this check as passed. |
| Live providers | **NOT RUN:** credentials and reachable sandbox services are required. |
| Full browser purchase E2E | **NOT RUN:** UI/provider composition is incomplete and owned by the laptop work. |

## Deliberately deferred beyond the demo

These are real launch requirements, but they should not distract from a truthful fixed-scenario demo:

- production OIDC/JWT identity, invitation, MFA/step-up, and session revocation;
- explicit buyer-organization/seller-organization marketplace grants;
- refund, cancellation, dispute, and compensation workflows;
- adoption, ROI, renewal, cancellation, and claim-accuracy learning;
- broad catalog retrieval, mutually exclusive/quantity-constrained optimization, multi-merchant execution, open RFP, and autonomous agent orchestration;
- production deployment, rate limits, telemetry, alerting, backup/restore, load tests, and provider quota controls;
- complete web component/accessibility/E2E coverage and non-critical visual polish.

## Claims boundary

The defensible demo claim is: **"SIRA deterministically evaluates seller-published SEIL evidence against a frozen company context, explains every gate and ordering decision, shows the generic counterfactual, and proposes an auditable Stackfile change."**

Do not yet claim production matching, live Senso intelligence, autonomous purchasing, verified entitlement from a real merchant, outcome learning, or a production-ready marketplace.
