# Demo Readiness Ledger

Updated: 2026-08-02

Branch reviewed: `core-backend`

Implementation reviewed through: `86ef60a`

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
| PAY-01 | **FIXED:** Approval expiry is rechecked at hosted-session creation, browser return, and final dispatch; stale authority becomes `EXPIRED` before side effects. | `47db419`. |
| PAY-02 | **FIXED:** Provider uncertainty and hosted-session failures are recoverable; malformed outbox events no longer starve later work. | `70dc0a3`. |
| PAY-03 | **FIXED:** Fulfillment retries separately from checkout, so paid-but-unfulfilled recovery does not repeat the charge. | `d6ee047`. |
| PAY-04 | **FIXED IN CODE:** Concurrent first idempotency claims use a savepoint, resolve the uniqueness race, and reread the canonical record. Live PostgreSQL proof is still open below. | `86ef60a`. |
| SEC-01 | **PASS IN CODE:** Production defaults fail closed, fixture adapters are labelled, tenant scoping/RLS policies exist, and the one-time Prava credential stays out of persistence, payloads, workflow history, and errors. | Production-boundary, provider, worker, and contract tests. |

## Required on the laptop for the demo

| ID | Priority | Required proof | Done when |
|---|---:|---|---|
| DEMO-01 | P0 | **Make fixture versus API mode unmistakable.** Arbitrary request text currently persists, but discovery still compiles the fixed ConsultCo/meeting-intelligence graph. | The demo is explicitly introduced as the fixed scenario, or two real persisted company contexts produce different frozen input hashes without the fixture loader. |
| DB-01 | P0 | **Run fresh PostgreSQL migrations with separate owner and runtime roles.** PostgreSQL is canonical; SQLite is not an acceptable substitute. | Alembic reaches head; runtime is `NOSUPERUSER`, `NOBYPASSRLS`, non-owner; forced RLS allows same-tenant access and denies cross-tenant access. |
| DB-02 | P0 | **Run the idempotency race against live PostgreSQL.** The code fix is tested with mocks but database transaction behavior has not been certified locally. | Two concurrent first requests produce one canonical idempotency record and no 500/duplicate intent. |
| DEMO-02 | P0 | **Complete one laptop startup smoke test.** | Fresh setup starts web/API/worker, health reports the expected mode, migrations are current, and the chosen scripted path survives a refresh without changing hashes/state. |
| UI-01 | P0, UI owner | **Wire or deliberately scope the visible journey.** | The user can complete the claimed demo path; unavailable provider actions remain disabled and honestly labelled rather than reporting fake success. |

Docker is not required for these checks. A local laptop PostgreSQL/Temporal setup or reachable services on the laptop can be used.

## Required only if the demo claims live sandbox purchasing

| ID | Blocker |
|---|---|
| LIVE-01 | Purchase Intent merchant, offer, quote, amount, currency, fulfillment, and patch must be derived from the exact selected persisted plan. They are still copied from the fixed fixture. |
| LIVE-02 | Validate the currency returned by Prava before merchant dispatch, not only merchant URL and amount. |
| LIVE-03 | Add approval revocation and enforce it through dispatch. Expiry is fixed; revocation is not implemented. |
| LIVE-04 | Configure authentic Prava, controlled merchant/entitlement, Temporal, and HTTPS return URL values and run the real sandbox contracts. Development adapters must remain visibly non-production. |
| LIVE-05 | Prove pending/timeout, unknown result, duplicate attempt, crash-after-charge, and paid-but-unfulfilled recovery against the sandbox without a duplicate charge. |
| LIVE-06 | Senso must be composed into typed, provenance-preserving input compilation before claiming that live company evidence affected the decision. |

Until those pass, demonstrate the deterministic transaction state machine with labelled fixtures only; do not describe it as a completed purchase.

## Important checks and known misses

| Check | Current evidence |
|---|---|
| Focused P0 regression | **PASS:** 133 tests. |
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
- broad catalog retrieval, multi-component dependency optimization, open RFP, and autonomous agent orchestration;
- production deployment, rate limits, telemetry, alerting, backup/restore, load tests, and provider quota controls;
- complete web component/accessibility/E2E coverage and non-critical visual polish.

## Claims boundary

The defensible demo claim is: **"SIRA deterministically evaluates seller-published SEIL evidence against a frozen company context, explains every gate and ordering decision, shows the generic counterfactual, and proposes an auditable Stackfile change."**

Do not yet claim production matching, live Senso intelligence, autonomous purchasing, verified entitlement from a real merchant, outcome learning, or a production-ready marketplace.
