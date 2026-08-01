# SIRA + SEIL Build Specification

**Purpose:** Short execution document for parallel implementation on two computers.  
**Master reference:** `PRD.md` remains authoritative for product intent, edge cases, and later lifecycle features.  
**Rule:** This document sequences the first complete vertical product path; it does not delete the broader product scope.

### Which document controls implementation?

- **BUILD_SPEC.md is the execution contract.** Agents implement its current sequence and definition of done.
- **PRD.md is a read-only reference.** Consult it only when BUILD_SPEC links to a concept, a security boundary is unclear, or later product scope is being designed.
- If the documents appear to conflict for the first build, stop the conflicting work and follow BUILD_SPEC until the product owner resolves it. Never silently expand the first assignment from the PRD.

## 1. Product in one sentence

SIRA uses private company context and a Stackfile to choose the best supported action among evaluated options; reusable SEIL Packs supply structured seller truth and honest anti-fit; an approved purchase is completed through Prava and verified through entitlement and stack updates.

## 2. First integrated product outcome

A user can:

1. Request a meeting-intelligence solution for a ten-person client-services team.
2. Review the private company facts SIRA used.
3. Compare four reusable product Packs:
   - one cheap product rejected by buyer policy as `SIRA_INELIGIBLE`;
   - one product returning a seller-authored `SEIL_PASS`;
   - one eligible runner-up;
   - one selected eligible plan.
4. See evidence, coverage, total cost, and the proposed Stackfile change.
5. Approve an exact locked Purchase Intent.
6. Enter the Prava hosted authorization flow.
7. Complete a genuine supported sandbox merchant authorization.
8. Verify the merchant order and expected entitlement.
9. See a decision-linked receipt and staged Stackfile update.

The demo must make the counterfactual obvious: a generic shopper chooses the cheapest option; company-aware SIRA chooses a different action for a specific, visible reason.

## 3. Non-negotiable product behavior

- PostgreSQL owns canonical typed state. Senso owns source ingestion/retrieval and provenance, not decisions.
- Models may extract and explain. Deterministic Python evaluates rules, scores plans, and checks authority.
- The seller receives only a sanitized Requirement Brief, never the Buyer Passport or hidden budget.
- `SIRA_INELIGIBLE` means a buyer/company rule failed. `SEIL_PASS` means the seller's published anti-fit rule fired. Do not conflate them.
- Published SEIL Pack rules must evaluate without a live seller agent.
- Seller positioning is visually labelled and has zero ranking effect.
- The recommended unit is a `SolutionPlan`; reuse/configure/no-action are valid even when the first demo selects a purchase.
- Approval binds the exact merchant, amount, currency, quote, Pack/offer versions, expected fulfillment, and decision hash.
- Prava credentials never enter the model, browser, logs, traces, Redis, database, or Temporal history.
- Payment success is not product success. Keep `PAYMENT_COMPLETED`, `PURCHASE_FULFILLED`, `DEPLOYMENT_ACTIVE`, and `OUTCOME_ACHIEVED` separate.
- No fake success endpoint may stand in for the required Prava plus merchant sandbox authorization.

### 3.1 Mirrored buyer and seller knowledge layers

SIRA and SEIL each use three layers. Private knowledge never becomes marketplace-visible merely because an agent retrieved it.

| Side | Private internal asset | Evaluated/shared asset | Context-specific output |
|---|---|---|---|
| Buyer/SIRA | Buyer Passport + Stackfile | Versioned Purchase Brief and evaluation gates | Sanitized seller-visible Requirement Brief |
| Seller/SEIL | Private Product Passport | Published immutable SEIL Pack | Buyer-specific positioning, structured plan, and offer |

The **Private Product Passport** contains seller-authorized product knowledge that must not all be published: source material, roadmap notes, availability/capacity, private negotiation bounds, fulfillment operations, approved positioning library, unpublished constraints, and Pack compilation history. A publication service derives a reviewed SEIL Pack using a field allowlist. Buyer-facing positioning and offers may use only approved Pack claims plus separately authorized commercial fields.

The **Purchase Brief** contains the buyer's internal request-specific rubric: desired outcome, stakeholders, hard gates, weighted preferences, known alternatives, Stackfile impact policy, disclosure choices, and approval requirements. It compiles a smaller Requirement Brief for sellers. Hidden budget, company identity, private failures, competing offers, employees, and unrestricted Stackfile data are denied by default.

### 3.2 Request-specific gates and calibration

Every request owns a versioned evaluation pipeline rather than relying on a universal fit score:

```text
availability -> buyer hard policy -> published SEIL anti-fit -> dependencies
-> implementation feasibility -> buyer preferences -> TCO -> final plan ordering
```

The buyer can inspect the gates and run a calibration or “dye test” using known examples: one product expected to fail, the incumbent/current approach, and one expected to qualify. Editing a gate or weight creates a new Purchase Brief and Decision version. Models may propose changes; only an authorized buyer role may accept them.

### 3.3 Feedback and engagement actions

For every candidate, the buyer may choose:

- `SHORTLIST`
- `PASS`
- `REQUEST_OFFER`
- `SAVE_FOR_LATER`
- `NOT_ENOUGH_EVIDENCE`

Feedback records a reason and may create a proposed request-specific criterion change. It never silently changes a hard company policy, global ranking rule, or Buyer Passport. `REQUEST_OFFER` starts a governed engagement; it does not immediately reveal private buyer identity or contact data.

### 3.4 Visibility and mutual consent

Every Purchase Request has one visibility mode:

- `PRIVATE`: SIRA searches/evaluates without seller outreach.
- `SELECTIVE`: SIRA sends an anonymized Requirement Brief only to explicitly selected SEILs.
- `OPEN_RFP`: qualified marketplace sellers may respond to the sanitized brief.

The first demo uses `SELECTIVE`. A seller may return `SEIL_PASS`, request an allowed missing field, or submit a structured offer. Buyer identity/contact details and seller contact details are exchanged only after the relevant parties consent to the engagement. Declining consent reveals no new contact or private context.

## 4. Locked implementation stack

| Layer | Choice |
|---|---|
| Repository | Git monorepo; `pnpm` workspaces for TypeScript and `uv` for Python |
| Web | Next.js App Router, React, TypeScript, Tailwind, shadcn/ui, TanStack Query |
| API | FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
| Core state | PostgreSQL |
| Agent runtime | OpenAI Agents SDK for Python behind an adapter |
| Evidence | Senso adapter |
| Payments | Prava hosted REST adapter for owned web UI |
| Durable work | Temporal adapter/workflows where installed; keep provider credentials outside histories |
| Tests | pytest/Hypothesis/respx/Testcontainers; Vitest/RTL/Playwright |
| Contracts | FastAPI OpenAPI plus generated TypeScript client and checked-in JSON schemas |

If a local dependency is unavailable, preserve the adapter and run a clearly labelled local development implementation. Never replace the production path with a hidden mock.

## 5. Repository shape

```text
apps/
  web/                         Next.js application
services/
  api/                         FastAPI HTTP control plane
  worker/                      workflow/background worker
python/
  domain/                      pure entities, enums, policy
  decision_engine/             deterministic eligibility and plan ranking
  stackfile/                   manifest, graph, patches
  agents/                      SIRA/SEIL orchestration and guardrails
  integrations/
    senso/
    prava/
    merchants/
  persistence/                 SQLAlchemy repositories and outbox
contracts/
  jsonschema/
  openapi/
fixtures/
  demo/
docs/
  PRD.md
  BUILD_SPEC.md
```

Domain modules must not import FastAPI, UI code, provider SDKs, or agent runtime code.

## 6. Parallel ownership

### Main PC — core owner

Owns all files except `apps/web/**` and web-only tests/assets:

- repository/bootstrap/tooling;
- domain schemas and enums;
- demo fixtures;
- FastAPI/OpenAPI;
- PostgreSQL/Alembic;
- deterministic decision engine;
- Stackfile graph and patch;
- SIRA/SEIL harness;
- Senso, Prava, and merchant adapters;
- approval, payment, fulfillment, receipt, and integration tests.

### Laptop — web owner

Owns:

- `apps/web/**`;
- web component/e2e tests;
- UI assets and design tokens;
- generated-client consumption, not generated contract output.

The laptop must not independently change API paths, shared enums, JSON schemas, fixtures, or backend behavior. It may add a written contract-change request. The main PC updates the contract and fixture first.

## 7. Git collaboration contract

- `main`: stable integration only.
- `core-backend`: main-PC implementation branch.
- `web-ui`: laptop implementation branch, created from the latest pushed integration point.
- Keep commits scoped to owned paths.
- Do not force-push shared branches.
- Before integration, both branches must be clean and pushed.
- Merge/rebase from the remote integration point before handing back work.
- Secrets and `.env` files are never committed.

## 8. Shared UI/API view contract

The backend must expose a UI-oriented decision view with this stable meaning. The exact generated type comes from OpenAPI.

```json
{
  "request": {
    "id": "req_demo",
    "intent": "Find meeting intelligence for ten consultants",
    "status": "DECISION_READY"
  },
  "company_context": {
    "facts_used": [],
    "hidden_fact_count": 0,
    "passport_version": 1,
    "stack_snapshot": 1
  },
  "coverage": {
    "evaluated_count": 4,
    "statement": "Best supported action among four executable Packs"
  },
  "candidates": [{
    "id": "fixture_selected_fit",
    "name": "Fixture D",
    "status": "ELIGIBLE",
    "reason_code": null,
    "reason": "Meets required privacy, identity, and integration rules",
    "preference_score": 86,
    "stack_risk": "LOW",
    "total_cost": {"amount": "89.00", "currency": "USD"},
    "evidence": [],
    "seller_positioning": null
  }],
  "selected_solution_plan": {},
  "stack_patch": {},
  "approval": {},
  "payment": {},
  "fulfillment": {},
  "receipt": null
}
```

Required shared enums:

```text
CandidateStatus = ELIGIBLE | ELIGIBLE_WITH_EXCEPTION | CONDITIONAL |
  SIRA_INELIGIBLE | SEIL_PASS | UNAVAILABLE | STALE_EVIDENCE |
  INSUFFICIENT_EVIDENCE | CONFLICTING_EVIDENCE | AUTHORITY_REQUIRED

ApprovalStatus = NOT_REQUESTED | PENDING | APPROVED | REJECTED | EXPIRED | SUPERSEDED

PaymentStatus = NOT_STARTED | SESSION_CREATED | CARDHOLDER_PENDING |
  CHECKOUT_PENDING | MERCHANT_APPROVED | REPORTING | PRAVA_COMPLETED |
  DECLINED | EXPIRED | UNCERTAIN | FAILED

FulfillmentStatus = NOT_STARTED | PENDING | PARTIAL | VERIFIED |
  FAILED_RETRYABLE | FAILED_FINAL | REVOKED

RequestVisibility = PRIVATE | SELECTIVE | OPEN_RFP

CandidateAction = SHORTLIST | PASS | REQUEST_OFFER |
  SAVE_FOR_LATER | NOT_ENOUGH_EVIDENCE

EngagementStatus = NOT_STARTED | SELLER_REVIEWING | SELLER_PASSED |
  OFFER_AVAILABLE | BUYER_CONSENT_PENDING | SELLER_CONSENT_PENDING |
  INTRODUCTION_READY | DECLINED | EXPIRED
```

## 9. Required API surface for the first build

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Runtime health |
| `POST` | `/v1/demo/reset` | Development/test-only deterministic fixture reset |
| `POST` | `/v1/purchase-requests` | Create request |
| `GET` | `/v1/purchase-requests/{id}` | Request/workflow summary |
| `POST` | `/v1/purchase-requests/{id}/discover` | Run governed comparison |
| `GET` | `/v1/purchase-requests/{id}/decision-view` | Complete UI projection above |
| `GET` | `/v1/purchase-requests/{id}/purchase-brief` | Buyer-authorized internal gates and versions |
| `GET` | `/v1/requirement-briefs/{id}` | Role-filtered sanitized seller view |
| `POST` | `/v1/purchase-requests/{id}/calibration-runs` | Dye-test known options through the gates |
| `POST` | `/v1/purchase-requests/{id}/candidates/{candidate_id}/actions` | Shortlist/pass/request offer/save/evidence feedback |
| `POST` | `/v1/engagements/{id}/consent` | Record scoped mutual-consent decision |
| `GET` | `/v1/decisions/{id}` | Decision Ledger and exact versions |
| `POST` | `/v1/decisions/{id}/purchase-intents` | Lock selected quote/action |
| `POST` | `/v1/purchase-intents/{id}/approval-requests` | Start approval |
| `POST` | `/v1/approval-requests/{id}/approve` | Authenticated exact-hash approval |
| `POST` | `/v1/purchase-intents/{id}/prava-sessions` | Create hosted Prava session |
| `GET` | `/v1/purchase-intents/{id}/status` | Reconciled payment/fulfillment state |
| `GET` | `/v1/purchases/{id}/receipt` | Decision-linked receipt |
| `GET` | `/v1/organizations/{id}/stackfile` | Current and proposed stack views |

Long operations return `202` with `workflow_id`, `status_url`, and `events_url`. The UI may initially poll `status_url`; SSE can follow without changing domain semantics.

## 10. Demo fixture

Check in deterministic, fictional data under `fixtures/demo/`:

- `buyer_passport.json`: private policy, stakeholders, budget/authority, operational preferences;
- `stackfile.yaml` and `stackfile.lock.json`;
- `purchase_brief.json` and its sanitized `requirement_brief.json`;
- one private `product_passport.json` per fictional seller, with publication tests proving private fields do not enter Packs;
- four SEIL Pack JSON files representing buyer rejection, seller pass, runner-up, and winner;
- evidence metadata and safe sample snippets;
- indicative offers and one live-quote fixture;
- expected Decision Ledger, Stackfile patch, approval payload, receipt, and entitlement.

Fixture tests must prove:

1. Removing private context changes the selected option to the cheapest candidate.
2. Adding private context produces one `SIRA_INELIGIBLE`.
3. Published seller rules produce one `SEIL_PASS` without buyer-private disclosure.
4. The winner and runner-up order are deterministic.
5. Seller positioning cannot change that order.
6. Calibration feedback creates a new Purchase Brief proposal/version rather than silently changing the existing result.
7. The seller-visible Requirement Brief contains no hidden buyer identity, budget, contacts, private failures, or unrestricted Stackfile fields.
8. `REQUEST_OFFER` in `SELECTIVE` mode reveals no contact details until the scoped engagement consent completes.

## 11. UI screens owned by the laptop

1. Product introduction and new request.
2. Request progress/loading states.
3. Company facts used, with provenance and privacy explanation.
4. Purchase Brief gates, visibility mode, disclosure preview, and calibration results.
5. Four-candidate comparison with unmistakable status/reason labels and feedback actions.
6. Selective `REQUEST_OFFER`, seller response, and mutual-consent state.
7. Generic-versus-company-aware counterfactual.
8. Selected Solution Plan and Stackfile patch.
9. Exact approval summary.
10. Prava redirect/pending/reconciliation states.
11. Merchant order, entitlement, receipt, and staged Stackfile result.
12. Error states for rejection, consent decline, expiry, payment decline, uncertainty, and paid-unfulfilled.

The UI must feel like a trustworthy procurement product, not a chatbot. Chat may collect intent, but decisions, evidence, approval, and payment use structured screens.

## 12. Implementation sequence

```text
Repository + contracts + fixtures
        |-----------------------> Laptop builds UI against fixtures
        v
Domain + decision engine + Stackfile
        v
FastAPI + persistence + approval
        v
Senso + Prava + merchant/fulfillment adapters
        v
Generated client + real API wiring
        v
Cross-branch integration + E2E proof
```

## 13. Definition of done for the first integrated build

1. Fresh setup instructions work on both computers without committed secrets.
2. Backend unit tests reproduce the four candidate states and selected plan.
3. OpenAPI generation and TypeScript client generation are repeatable.
4. Web UI renders every required screen from fixture and real API modes.
5. Buyer-private fields are absent from the seller-facing brief and UI network payloads not authorized for the current role.
6. Private Product Passport fields excluded from the Pack cannot appear in buyer APIs, seller positioning, prompts, traces, or fixtures intended for buyers.
7. Candidate feedback and calibration changes create explicit versions; an unaccepted proposal has zero ranking effect.
8. Selective engagement reveals no party's contact details until scoped mutual consent is recorded.
9. Approval changes to `SUPERSEDED` after any material Purchase Intent mutation.
10. Duplicate execution requests cannot create a second merchant order or entitlement.
11. A real supported Prava sandbox authorization reaches a genuine merchant/processor sandbox path.
12. Merchant result is reported/reconciled and expected entitlement is verified.
13. Receipt links request, decision, Pack/offer/quote versions, approval, Prava references, merchant order, amount, and entitlement.
14. The Stackfile proposed/staged change is visible and not falsely marked as active deployment.
15. Playwright demonstrates the complete request-to-receipt path plus consent decline, payment decline, and uncertain-payment recovery views.

## 14. Not part of the first parallel assignment

These remain in the master PRD but must not create cross-laptop conflicts before the integrated path works:

- full enterprise onboarding/SCIM;
- production marketplace onboarding and reputation;
- continuous optimizer and OR-Tools portfolio UI;
- renewals, mandates, cancellations, and cross-tenant learning;
- every software category beyond the locked meeting-intelligence fixture.

Do not delete their abstractions or make schema choices that prevent them. Simply do not implement their full UI/workflows in the first parallel branches.
