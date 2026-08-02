# SIRA Build Specification

**Purpose:** Execution contract for the first complete SIRA workflow.
**Master reference:** `PRD.md` remains authoritative for product intent, edge cases, and later lifecycle features.  
**Rule:** This document sequences the first complete vertical product path; it does not delete the broader product scope.

### Which document controls implementation?

- **BUILD_SPEC.md is the execution contract.** Agents implement its current sequence and definition of done.
- **PRD.md is a read-only reference.** Consult it only when BUILD_SPEC links to a concept, a security boundary is unclear, or later product scope is being designed.
- If the documents appear to conflict for the first build, stop the conflicting work and follow BUILD_SPEC until the product owner resolves it. Never silently expand the first assignment from the PRD.

## 1. Product in one sentence

SIRA uses its Decision Graph to turn private company context, Stackfile state, and reusable SEIL Product Evidence into the best supported executable action among evaluated options; it explains uncertainty, obtains approval, executes the action when needed, and verifies the result.

## 2. First integrated product outcome

A user can:

1. Open an upcoming meeting-intelligence renewal for a ten-person client-services team with an incumbent contract, cancellation deadline, usage, and outcome history.
2. Review the private company facts SIRA used.
3. Compare complete action plans: renew, resize, configure, cancel, or keep the incumbent, plus four reusable Pack-backed replacement options:
   - one cheap product rejected by buyer policy as `SIRA_INELIGIBLE`;
   - one product returning a seller-authored `SEIL_PASS`;
   - the incumbent renewal/resize plan as an eligible runner-up;
   - one selected eligible replacement plan.
4. See evidence, coverage, total cost, and the proposed Stackfile change.
5. See conservative/optimistic preference bounds, rank stability, and the missing evidence that could change the result.
6. Approve an exact locked Purchase Intent.
7. Enter the Prava hosted authorization flow.
8. Complete a genuine supported sandbox merchant authorization.
9. Verify the merchant order and expected entitlement.
10. See a decision-linked receipt and staged Stackfile update.

The demo must make the counterfactual obvious: a generic replacement search chooses the cheapest option; company-aware SIRA chooses a different renewal action for a specific, visible company/Stack fact.

The production launch wedge is a governed meeting-intelligence renewal for 20-200-person client-service firms. The hackathon's new purchase remains the first integrated transaction proof; it does not broaden the first build into a general marketplace.

## 3. Non-negotiable product behavior

- PostgreSQL owns canonical typed state. Senso owns source ingestion/retrieval and provenance, not decisions.
- SIRA is the visible buyer product. SEIL is the seller-controlled Product Evidence protocol/service; the buyer UI must not depict two agents chatting.
- Models may extract and explain. Deterministic Python evaluates rules, scores plans, and checks authority.
- The seller receives only a sanitized Requirement Brief, never the Buyer Passport or hidden budget.
- `SIRA_INELIGIBLE` means a buyer/company rule failed. `SEIL_PASS` means the seller's published anti-fit rule fired. Do not conflate them.
- Published SEIL Pack rules must evaluate without a live seller agent.
- Seller positioning is visually labelled and has zero ranking effect.
- The recommended unit is a `SolutionPlan`; reuse/configure/no-action are valid even when the first demo selects a purchase.
- The UI exposes preference fit, Stack risk, TCO, evidence, coverage, and rank stability separately. It never presents a single opaque fit percentage.
- Approval binds the exact merchant, amount, currency, quote, Pack/offer versions, expected fulfillment, and decision hash.
- Prava credentials never enter the model, browser, logs, traces, Redis, database, or Temporal history.
- Payment success is not product success. Keep `PAYMENT_COMPLETED`, `PURCHASE_FULFILLED`, `DEPLOYMENT_ACTIVE`, and `OUTCOME_ACHIEVED` separate.
- No fake success endpoint may stand in for the required Prava plus merchant sandbox authorization.

### 3.1 Separated buyer and seller knowledge layers

SIRA and SEIL retain symmetric trust boundaries but not symmetric product surfaces. Buyers use SIRA; SEIL initially operates through backend publication/qualification plus a lightweight vendor claim-and-correct flow. Private knowledge never becomes marketplace-visible merely because an agent retrieved it.

| Side | Private internal asset | Evaluated/shared asset | Context-specific output |
|---|---|---|---|
| Buyer/SIRA | Buyer Passport + Stackfile | Versioned Purchase Brief and evaluation gates | Sanitized seller-visible Requirement Brief |
| Seller/SEIL | Private Product Passport | Published immutable SEIL Pack | Buyer-specific positioning, structured plan, and offer |

The **Private Product Passport** contains seller-authorized product knowledge that must not all be published: source material, roadmap notes, availability/capacity, private negotiation bounds, fulfillment operations, approved positioning library, unpublished constraints, and Pack compilation history. A publication service derives a reviewed SEIL Pack using a field allowlist. Buyer-facing positioning and offers may use only approved Pack claims plus separately authorized commercial fields.

The **Purchase Brief** contains the buyer's internal request-specific rubric: desired outcome, stakeholders, hard gates, weighted preferences, known alternatives, Stackfile impact policy, disclosure choices, and approval requirements. It compiles a smaller Requirement Brief for sellers. Hidden budget, company identity, private failures, competing offers, employees, and unrestricted Stackfile data are denied by default.

### 3.2 Request-specific gates and calibration

Every request owns a versioned evaluation pipeline rather than relying on a universal fit score:

```text
option recall/deduplication -> availability -> evidence readiness
-> buyer hard policy -> published SEIL anti-fit -> dependencies
-> implementation feasibility -> Solution Plan construction
-> buyer preferences/Stack risk/TCO/evidence -> robustness -> final ordering
```

All gate families evaluate and persist their reasons. If several blocking states apply, the headline status uses this fixed precedence:

`UNAVAILABLE -> CONFLICTING_EVIDENCE -> STALE_EVIDENCE -> INSUFFICIENT_EVIDENCE -> SIRA_INELIGIBLE -> SEIL_PASS -> AUTHORITY_REQUIRED -> ADVISORY_ONLY -> CONDITIONAL -> ELIGIBLE_WITH_EXCEPTION -> ELIGIBLE`.

`ADVISORY_ONLY` is reserved for platform-compiled or external-unsealed Product Evidence that may support research but lacks seller publication authority. Its public projection is `RESEARCH_ONLY`. It cannot enter executable ordering, produce `SEIL_PASS`, create a Purchase Intent, or expose an execute control; it may enter the resolution frontier when seller sealing, evidence, merchant, or offer normalization can make it executable.

The buyer can inspect the gates and run a **Calibration check** using known examples: one product expected to fail, the incumbent/current approach, and one expected to qualify. Editing a gate or weight creates a new Purchase Brief and Decision version. Models may propose changes; only an authorized buyer role may accept them.

### 3.3 Feedback and engagement actions

For every solution option, the buyer may choose:

- `KEEP_FOR_COMPARISON`
- `ELIMINATE`
- `ASK_VENDOR`
- `SAVE`
- `NEED_EVIDENCE`

Feedback records a reason and may create a proposed request-specific criterion change. It never silently changes a hard company policy, global ranking rule, or Buyer Passport. `ASK_VENDOR` starts a governed engagement; it does not immediately reveal private buyer identity or contact data.

The public API uses procurement-native values. Legacy internal aliases may be accepted only during a declared migration window and are never emitted by the current OpenAPI contract:

| API value | Buyer-facing label |
|---|---|
| `KEEP_FOR_COMPARISON` | Keep for comparison |
| `ELIMINATE` | Eliminate |
| `ASK_VENDOR` | Ask vendor |
| `SAVE` | Save |
| `NEED_EVIDENCE` | Need evidence |

### 3.4 Visibility and mutual consent

Every Decision request has one visibility mode:

- `PRIVATE`: SIRA searches/evaluates without seller outreach.
- `SELECTIVE`: SIRA sends an anonymized Requirement Brief only to explicitly selected SEILs.
- `OPEN_RFP`: qualified marketplace sellers may respond to the sanitized brief.

The first demo uses `SELECTIVE`. A seller may return `SEIL_PASS`, request an allowed missing field, or submit a structured offer. Buyer identity/contact details and seller contact details are exchanged only after the relevant parties consent to the engagement. Declining consent reveals no new contact or private context.

### 3.5 SIRA Decision Graph v1

The first build must implement the full deterministic path below; callers must not supply precomputed “fit” as authoritative input:

1. **Compile brief:** freeze Purchase Brief, Company Profile, Stackfile, taxonomy, policy, and engine versions.
2. **Recall and deduplicate:** evaluate all four Pack fixtures; add feasible current-stack/no-action alternatives and, for the renewal fixture, renew/resize/cancel alternatives. Resolve aliases, editions, sellers, resellers, regions, and offers to canonical identities.
3. **Assess evidence:** for every decision-material claim record allowed source class, verification method, scope match, reconstructability, freshness, dispute/revocation state, and supported criterion.
4. **Run tri-state gates:** each gate emits `TRUE`, `FALSE`, `UNKNOWN`, or `CONFLICT` plus all reasons; the deterministic primary status follows Section 3.2 precedence. Missing evidence never becomes a fabricated policy pass/fail.
5. **Build plans:** construct candidate `SolutionPlan` records with dependency closure, a stable ordered action/component hash, and lifecycle `CANDIDATE`. Gates and permitted resolutions then derive `RESOLUTION_PENDING`, `EXECUTABLE`, or `BLOCKED`; construction alone never implies executability.
6. **Calculate dimensions:** compute plan-level conservative and optimistic preference score, Stack-risk interval, low/base/high TCO, hard and decision-material evidence coverage, evidence-age interval, universe coverage, and unresolved/conflicting counts. Scores use exact numerator/denominator values; two-place half-even decimals are display only.
7. **Order:** use the PRD's lexicographic ordering with conservative preference score only.
8. **Test robustness:** evaluate every declared interval in the authoritative ordering—preference, Stack risk, TCO, decision-material evidence coverage, and freshness. Decision-level `rank_stability` is `STABLE` only when no competing plan's optimistic envelope can beat the selected plan's conservative envelope. Conditional/stale/insufficient plans enter the frontier only with an exact permitted resolution; failed non-overridable gates never do. Missing bound rules yield `UNDETERMINED` and block autonomous execution. Per-plan `ordering_frontier_member`, `resolution_frontier_member`, and quote-policy fields are separate from decision-level stability.
9. **Compute counterfactual:** freeze the universe and every Pack/offer/quote/taxonomy/normalization/context/stack/pipeline/engine version, rerun request-only context, then enumerate fact removals by ascending cardinality and stable fact ID up to three. Persist the smallest winner-changing set, deterministic tie-break, alternatives, tested limit, and before/after hashes; otherwise return `NO_SMALL_COUNTERFACTUAL_FOUND`.
10. **Persist ledger:** store every input/pipeline version, included/excluded option, gate, score component, evidence assessment, counterfactual, and output needed to reproduce the canonical decision payload and hash. Generated record IDs and timestamps are outside that canonical hash.

Model output may propose typed inputs and narrate the resulting ledger. It cannot set eligibility, evidence confidence, rank, decisive counterfactual facts, or authority.

Every preference-capable taxonomy field must provide a finite enum/domain or numeric bounds, a total normalization rule, and an unknown-bound rule. Every plan aggregation operator must provide exact interval propagation. Missing/custom bound logic produces `BOUND_UNAVAILABLE`; it never silently assumes a best case.

Non-preference robustness is also exact:

- map Stack-risk tiers `LOW=0`, `MEDIUM=1`, `HIGH=2`, `CRITICAL=3`; plan lower/base/upper is the maximum corresponding ordinal across required components and risk dimensions;
- derive every component/dimension Stack-risk bound only through the versioned category `risk_rule_set`. Each rule has a stable rule ID, `dimension_id`, action/component scope, normalized input paths, a total predicate over closed domains, emitted tier, and explicit missing-input bound. Base uses observed/base values; lower and upper evaluate the declared input intervals and permitted resolutions. Within one component and `dimension_id`, each bound is the `MAX` emitted ordinal across every simultaneously triggered rule; rule order/priority has no effect. No triggered rule yields `LOW` only when the rule set declares complete input coverage; otherwise emit `BOUND_UNAVAILABLE`. Persist triggered rule IDs and input hashes. Model output cannot assign a risk tier;
- use TCO high for the conservative envelope, low for the optimistic envelope, and base for final ordering;
- for applicable non-hard decision-material criteria, persist category `coverage_weight` 1–5 and compute exact weighted coverage. A criterion is covered only when its plan-level value has acceptable current evidence for every component/value required by the aggregation rule; duplicate claims/sources do not add denominator items. Optimistic coverage may add only typed permitted evidence resolutions;
- freeze `evaluated_at`; compute each evidence-age lower/upper ratio from observed-time bounds divided by SLA seconds, then take the plan-level maximum.

Outcome-history priors are explicit policy inputs, not evidence. Every enabled outcome criterion declares an exact rational `neutral_prior`; the locked v1 fixture uses `1/2`. A plan with no product-specific outcome history receives that value for criterion satisfaction in both preference bounds, contributes zero to evidence coverage for that criterion, cannot satisfy a hard gate with the prior, and is labelled **category prior—not observed outcome**. Missing optional evidence for every other criterion contributes zero. Prior values, policy version, and applicability are hashed and shown in the ledger.

Any missing risk/TCO/coverage/time bound produces `BOUND_UNAVAILABLE`, `rank_stability=UNDETERMINED`, and no autonomous execution.

Required persisted Decision Graph records:

- `evaluation_runs` and `evaluation_pipeline_versions`;
- `discovery_runs`, `candidate_set_members`, and `identity_merges`;
- `decision_gate_results` and `evidence_assessments`;
- `solution_plan_components`, `score_components`, and `score_bounds`;
- `robustness_frontiers` and `counterfactual_records`.

Each `evaluation_run` references exact request, Company Profile, Stackfile, Registry/candidate set, Pack, offer/quote, taxonomy, normalization, policy, FX, pipeline, and engine versions. First compute an `evaluation_payload_hash` over the ordered base evaluation. Counterfactual records refer only to base/alternate evaluation payload hashes. The final canonical `decision_hash` covers the base evaluation hash, ordered counterfactual-record hashes, and selected outcome; it excludes generated database IDs/timestamps and has no self-reference.

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

## 6. Implementation boundaries

- Canonical contracts change schema-first: update closed JSON Schema/OpenAPI, regenerate clients, and then update producers, consumers, fixtures, and tests in the same change.
- Backend and web may evolve independently only while they preserve the frozen contract and fixture semantics.
- Domain modules must remain independent of FastAPI, UI, provider SDKs, and agent runtime code.
- Keep commits scoped, never commit secrets or `.env` files, and do not force-push shared branches.

## 8. Shared UI/API view contract

The backend must expose a UI-oriented decision view with this stable meaning. The exact generated type comes from OpenAPI.

```json
{
  "request": {
    "id": "req_demo",
    "intent": "Review the meeting-intelligence renewal for ten consultants",
    "status": "DECISION_READY",
    "decision_version": 3,
    "decision_state": "CURRENT",
    "superseded_by": null
  },
  "workflow": {
    "current_stage": "ACTION",
    "actor": {
      "role": "DECISION_MAKER",
      "capabilities": ["VIEW_DECISION", "SELECT_PLAN"]
    },
    "available_actions": [{
      "id": "START_REVIEW",
      "label": "Review action plan",
      "method": "POST",
      "href": "/v1/decisions/dec_demo_v3/action-runs",
      "requires_confirmation": false
    }],
    "blocking_tasks": [],
    "active_operation": null,
    "stage_history": [
      {
        "stage": "NEED",
        "status": "COMPLETED",
        "checkpoint_id": "cp_need_v3",
        "completed_at": "2026-08-02T09:05:00Z",
        "href": "/decisions/req_demo/versions/3/need"
      },
      {
        "stage": "COMPANY_FIT",
        "status": "COMPLETED",
        "checkpoint_id": "cp_fit_v3",
        "completed_at": "2026-08-02T09:12:00Z",
        "href": "/decisions/req_demo/versions/3/company-fit"
      },
      {
        "stage": "OPTIONS",
        "status": "COMPLETED",
        "checkpoint_id": "cp_options_v3",
        "completed_at": "2026-08-02T09:16:00Z",
        "href": "/decisions/req_demo/versions/3/options"
      },
      {
        "stage": "ACTION",
        "status": "CURRENT",
        "checkpoint_id": "cp_action_v3",
        "completed_at": null,
        "href": "/decisions/req_demo/versions/3/action"
      }
    ],
    "version_links": {
      "current": "/decisions/req_demo/versions/3/action",
      "previous": "/decisions/req_demo/versions/2/action",
      "superseded_by": null
    }
  },
  "evaluation": {
    "id": "eval_demo_v3",
    "payload_hash": "sha256:...",
    "decision_hash": "sha256:...",
    "pipeline_version": "decision_graph_v1",
    "engine_version": "engine_v1"
  },
  "company_context": {
    "facts_used": [],
    "hidden_fact_count": 0,
    "company_profile_version": 1,
    "company_stack_snapshot": 1
  },
  "coverage": {
    "raw_record_count": 6,
    "product_evidence_option_count": 4,
    "canonical_product_count": 4,
    "duplicate_count": 0,
    "generated_solution_plan_count": 10,
    "evaluated_solution_plan_count": 10,
    "excluded_count": 0,
    "statement": "Best supported action among four products and six current-stack/contract actions"
  },
  "decision_outcome": "SELECTED_SOLUTION_PLAN",
  "rank_stability": {
    "status": "STABLE",
    "summary": "The recommended action stays first across the supported uncertainty ranges",
    "evidence_frontier": []
  },
  "solution_options": [{
    "id": "sol_replace_fixture_d",
    "action_type": "REPLACE",
    "label": "Replace the incumbent with Fixture D",
    "status": "SUPPORTED",
    "reason_code": null,
    "reason": "Meets required privacy, identity, and integration rules",
    "default_comparison": {
      "cost": {"amount": "89.00", "currency": "USD", "horizon_days": 30},
      "stack_change": "Replace one incumbent; retain Slack and Google Workspace",
      "next_action": "Review plan"
    },
    "preference_score": {
      "conservative": {"numerator": 86, "denominator": 1, "display": "86.00"},
      "optimistic": {"numerator": 92, "denominator": 1, "display": "92.00"}
    },
    "ordering_frontier_member": true,
    "resolution_frontier_member": false,
    "quote_required": true,
    "quote_policy_reason": "SELECTED_PLAN",
    "permitted_resolution": null,
    "stack_risk": {"base": "LOW", "lower": "LOW", "upper": "MEDIUM"},
    "total_cost": {
      "low": {"amount": "89.00", "currency": "USD"},
      "base": {"amount": "89.00", "currency": "USD"},
      "high": {"amount": "109.00", "currency": "USD"}
    },
    "evidence_coverage": {
      "hard": {"numerator": 1, "denominator": 1},
      "decision_material": {
        "conservative": {"numerator": 7, "denominator": 8},
        "optimistic": {"numerator": 8, "denominator": 8}
      }
    },
    "maximum_evidence_age_ratio": {
      "lower": {"numerator": 12, "denominator": 90},
      "upper": {"numerator": 20, "denominator": 90}
    },
    "evidence_frontier": [],
    "components": [{
      "product_evidence_id": "fixture_selected_fit",
      "action": "ADD",
      "publisher_authority": "SELLER_SEALED",
      "verification_summary": "8 verified, 2 seller-asserted, 0 stale"
    }],
    "merchant": {"id": "merchant_demo", "offer_id": "offer_demo"},
    "evidence": [],
    "seller_positioning": null
  }],
  "selected_action_plan": {
    "id": "sol_replace_fixture_d",
    "action_type": "REPLACE",
    "state": "SELECTED",
    "selected_at": "2026-08-02T09:16:00Z",
    "selected_by_role": "DECISION_MAKER",
    "selection_id": "selection_demo_v3",
    "decision_version": 3,
    "decision_hash": "sha256:...",
    "execution_steps": [
      {
        "id": "step_review",
        "type": "REVIEW",
        "status": "AVAILABLE",
        "owner_role": "DECISION_MAKER",
        "started_at": null,
        "completed_at": null,
        "checkpoint_id": null,
        "artifact_id": null,
        "blocker": null,
        "available_action": {
          "id": "START_REVIEW",
          "label": "Review action plan",
          "method": "POST",
          "href": "/v1/decisions/dec_demo_v3/action-runs",
          "requires_confirmation": false
        }
      },
      {
        "id": "step_authority",
        "type": "REQUIRED_AUTHORITY",
        "status": "NOT_REACHED",
        "owner_role": "BUDGET_OWNER",
        "started_at": null,
        "completed_at": null,
        "checkpoint_id": null,
        "artifact_id": null,
        "blocker": null,
        "available_action": null
      },
      {
        "id": "step_execute",
        "type": "EXECUTE_OR_ASSIGN",
        "status": "NOT_REACHED",
        "owner_role": "CARDHOLDER",
        "started_at": null,
        "completed_at": null,
        "checkpoint_id": null,
        "artifact_id": null,
        "blocker": null,
        "available_action": null
      },
      {
        "id": "step_verify",
        "type": "VERIFY",
        "status": "NOT_REACHED",
        "owner_role": "IT_OPERATIONS",
        "started_at": null,
        "completed_at": null,
        "checkpoint_id": null,
        "artifact_id": null,
        "blocker": null,
        "available_action": null
      }
    ],
    "href": "/v1/decisions/dec_demo_v3/solution-plans/sol_replace_fixture_d"
  },
  "stack_change": {
    "id": "sp_demo_v3",
    "status": "PROPOSED",
    "summary": "Add Fixture D, stage incumbent retirement, retain two dependencies",
    "added": ["product_fixture_d"],
    "removed": [],
    "staged_for_removal": ["instance_incumbent"],
    "retained": ["slack", "google_workspace"],
    "dependency_changed": ["meeting_capture"],
    "href": "/v1/stack-patches/sp_demo_v3"
  },
  "approval": {
    "required": true,
    "status": "NOT_REQUESTED",
    "requirement_set_id": "aprs_demo_v3",
    "owner_roles": ["BUDGET_OWNER", "IT_OPERATIONS"],
    "completed_count": 0,
    "required_count": 2,
    "rejected_by_role": null,
    "expires_at": null,
    "href": "/v1/decisions/dec_demo_v3/approval"
  },
  "payment": {
    "required": true,
    "status": "NOT_STARTED",
    "currency": "USD",
    "line_items": [
      {"type": "MERCHANT_SUBTOTAL", "amount": "87.00"},
      {"type": "SIRA_TRANSACTION_FEE", "amount": "2.00", "schedule_version": "buyer_txn_demo_v1"}
    ],
    "landed_total": "89.00",
    "purchase_intent_id": null,
    "last_checkpoint_at": null,
    "href": null
  },
  "fulfillment": {
    "required": true,
    "status": "NOT_STARTED",
    "expected_item_count": 2,
    "verified_item_count": 0,
    "partial_item_count": 0,
    "owner_role": "IT_OPERATIONS",
    "last_checkpoint_at": null,
    "href": null
  },
  "result_artifacts": [],
  "receipt": null
}
```

`solution_options` is the buyer projection because complete Solution Plans—not Pack candidates—are ranked. Component-level candidate evaluations remain in the detailed Decision Ledger only. A solution option may contain zero, one, or many Pack/current-instance components; `REUSE_EXISTING`, `CONFIGURE_EXISTING`, `NO_ACTION`, and `CANCEL` use the same action-neutral shape with no new-product component and `merchant: null`. `RENEW` and `RESIZE` reference the incumbent instance and current contract/quote.

`rank_stability` belongs to the decision. Per option, `ordering_frontier_member`, `resolution_frontier_member`, and `quote_required/quote_policy_reason` remain distinct. Raw rational score/coverage/age bounds, evidence frontier, provenance, and calculations appear only in the evidence/ledger drawer; the default comparison row shows support status, comparable cost, Stack change, and next action. The server owns stage, actor capabilities, available actions, blockers, active operation, and version/supersession state. The frontend never infers authority from status.

Each available-action descriptor contains stable action ID, localized label, method, href, confirmation requirement, and optional expiry. Each blocking task contains task ID, safe title, owner role, due/expiry time, status, and authenticated href. A non-null `active_operation` contains operation ID/kind/status, current and last-successful checkpoint, owner role, started/updated timestamps, retryability, safe-to-leave flag, and only the server-authorized recovery action. Unauthorized actions/tasks are omitted rather than disabled with leaked context.

`stage_history` and `version_links` are the Decision Path source of truth. Every stage entry has stage, status, checkpoint ID, completion timestamp, and stable href. The client never fabricates completion from route position. `selected_action_plan`, `stack_change`, `approval`, `payment`, and `fulfillment` are always either `null` when not yet created or the typed object above—never an untyped empty object. `result_artifacts` contains stable ID, `ResultArtifactType`, verification state, actor/owner, occurred/verified timestamps, safe label, href, and related Stack patch/receipt ID.

Plan selection is a dedicated authoritative operation, not option feedback. `POST /v1/decisions/{id}/plan-selections` accepts only `solution_plan_id`, source `decision_version`, source `decision_hash`, and an idempotency key. The server verifies current version, selectable status, stability/exception authority, actor capability, and the frozen Solution Plan hash. A successful non-retry creates an immutable new Decision version containing `selection_id` and `selected_action_plan`; every downstream approval/action binds that version. An exact retry returns the same selection. Reselecting creates another version and supersedes any Purchase Intent, approval, or action run from the prior selection. A zero-charge selection exposes an action run directly and never creates a Purchase Intent, Prava state, or fee.

`selected_action_plan.execution_steps` is the Execution Timeline source of truth. Every step has stable ID, closed type/status, owner role, timestamps, checkpoint/artifact references, safe blocker, and at most one server-authorized action. Payment and merchant fulfillment are represented only inside an applicable `EXECUTE_OR_ASSIGN` or `VERIFY` branch; the client never invents permanent payment steps from `action_type`.

The buyer-paid SIRA transaction fee is a separate line item with a versioned published schedule. For the first integrated sandbox only, `buyer_txn_demo_v1` is a flat **USD 2.00 once per charge-bearing Purchase Intent**, with no percentage basis, no additional minimum/cap calculation, no tax calculation, and no fee on retries, zero-charge actions, or non-transaction actions. This amount is demo policy, not a validated production price. It is included once in the option's low/base/high TCO, `payment.landed_total`, the exact Purchase Intent/approval hash, and receipt. It creates no seller-specific or policy/rank boost; its only ordering effect is through ordinary disclosed buyer TCO, so it may distinguish a charge-bearing plan from a zero-charge plan. Seller-paid referral/success commission is prohibited. Zero-charge or non-transaction actions set `payment.required=false` and `payment.status=NOT_REQUIRED`, omit Purchase Intent/Prava actions, and create no transaction fee.

When `decision_outcome = NO_ELIGIBLE_SUPPORTED_ACTION`, `selected_action_plan` is null and the Options stage renders a dedicated result containing evaluated/excluded counts, exact blocking reasons, evidence/category limitations, and server-provided safe next actions. It is not an empty state.

Component evaluation states remain canonical in the detailed ledger. The public solution-option projection uses procurement-native status values:

| Component/ledger state | Solution-option API value | Buyer-facing label |
|---|---|---|
| `ELIGIBLE` | `SUPPORTED` | Supported |
| `ELIGIBLE_WITH_EXCEPTION` | `SUPPORTED_WITH_EXCEPTION` | Supported with approved exception |
| `CONDITIONAL` | `NEEDS_CONDITION` | Needs a condition resolved |
| `SIRA_INELIGIBLE` | `BLOCKED_BY_COMPANY_REQUIREMENT` | Blocked by company requirement |
| `SEIL_PASS` | `VENDOR_NOT_SUPPORTED` | Vendor says not supported |
| `INSUFFICIENT_EVIDENCE` / `STALE_EVIDENCE` | `NEEDS_EVIDENCE` | Needs evidence |
| `CONFLICTING_EVIDENCE` | `EVIDENCE_CONFLICT` | Evidence conflict |
| `UNAVAILABLE` | `UNAVAILABLE` | Unavailable |
| `AUTHORITY_REQUIRED` | `AUTHORITY_REQUIRED` | Needs an authorized owner |
| `ADVISORY_ONLY` | `RESEARCH_ONLY` | Research only |

Required shared enums:

```text
ComponentStatus = ELIGIBLE | ELIGIBLE_WITH_EXCEPTION | CONDITIONAL |
  SIRA_INELIGIBLE | SEIL_PASS | UNAVAILABLE | STALE_EVIDENCE |
  INSUFFICIENT_EVIDENCE | CONFLICTING_EVIDENCE | AUTHORITY_REQUIRED |
  ADVISORY_ONLY

SolutionOptionStatus = SUPPORTED | SUPPORTED_WITH_EXCEPTION |
  NEEDS_CONDITION | BLOCKED_BY_COMPANY_REQUIREMENT |
  VENDOR_NOT_SUPPORTED | UNAVAILABLE | NEEDS_EVIDENCE |
  EVIDENCE_CONFLICT | AUTHORITY_REQUIRED | RESEARCH_ONLY

DecisionOutcome = SELECTED_SOLUTION_PLAN | NO_ELIGIBLE_SUPPORTED_ACTION

RankStability = STABLE | UNSTABLE | UNDETERMINED

PackAuthority = SELLER_SEALED | PLATFORM_COMPILED | EXTERNAL_UNSEALED

SolutionActionType = REUSE_EXISTING | CONFIGURE_EXISTING | NO_ACTION |
  BUY | RENEW | RESIZE | REPLACE | CONSOLIDATE | CANCEL

SolutionPlanLifecycle = CANDIDATE | RESOLUTION_PENDING | EXECUTABLE | BLOCKED

PlanSelectionState = SELECTED | SUPERSEDED | CANCELLED

DecisionStage = NEED | COMPANY_FIT | OPTIONS | ACTION | RESULT

StageStatus = NOT_STARTED | READY | CURRENT | WAITING | BLOCKED |
  COMPLETED | SUPERSEDED

DecisionVersionState = CURRENT | SUPERSEDED

OperationStatus = QUEUED | RUNNING | WAITING_FOR_HUMAN |
  RETRYABLE_ERROR | UNCERTAIN | COMPLETED | FAILED_FINAL

ExecutionStepType = REVIEW | REQUIRED_AUTHORITY | EXECUTE_OR_ASSIGN | VERIFY

ExecutionStepStatus = NOT_REACHED | AVAILABLE | CURRENT | BLOCKED |
  COMPLETED | SKIPPED | FAILED_RETRYABLE | FAILED_FINAL

ApprovalStatus = NOT_REQUIRED | NOT_REQUESTED | PENDING | APPROVED |
  REJECTED | EXPIRED | SUPERSEDED

PaymentStatus = NOT_REQUIRED | NOT_STARTED | SESSION_CREATED | CARDHOLDER_PENDING |
  CHECKOUT_PENDING | MERCHANT_APPROVED | REPORTING | PRAVA_COMPLETED |
  DECLINED | EXPIRED | UNCERTAIN | FAILED

FulfillmentStatus = NOT_REQUIRED | NOT_STARTED | PENDING | PARTIAL | VERIFIED |
  FAILED_RETRYABLE | FAILED_FINAL | REVOKED

RequestVisibility = PRIVATE | SELECTIVE | OPEN_RFP

ActorRole = REQUESTER | DECISION_MAKER | POLICY_REVIEWER | BUDGET_OWNER |
  PROCUREMENT | CARDHOLDER | IT_OPERATIONS | AUDITOR | SELLER_EDITOR |
  SELLER_REVIEWER | PLATFORM_OPERATOR

UIActionCapability = VIEW_DECISION | EDIT_REQUEST | ANSWER_TASK |
  VIEW_PRIVATE_COMPANY_FACTS | KEEP_OPTION | ELIMINATE_OPTION | ASK_VENDOR |
  SAVE_OPTION | REQUEST_EVIDENCE | SELECT_PLAN | ACCEPT_EXCEPTION |
  APPROVE_POLICY | APPROVE_BUDGET | AUTHORIZE_PAYMENT |
  EXECUTE_CONFIGURATION | VERIFY_FULFILLMENT | PROVIDE_OUTCOME |
  EXPORT_AUDIT | EDIT_PRODUCT_EVIDENCE | REVIEW_PRODUCT_EVIDENCE |
  PUBLISH_PRODUCT_EVIDENCE | SUSPEND_PRODUCT_EVIDENCE

OptionFeedbackAction = KEEP_FOR_COMPARISON | ELIMINATE | ASK_VENDOR |
  SAVE | NEED_EVIDENCE

EngagementStatus = NOT_STARTED | SELLER_REVIEWING | SELLER_PASSED |
  OFFER_AVAILABLE | BUYER_CONSENT_PENDING | SELLER_CONSENT_PENDING |
  INTRODUCTION_READY | DECLINED | EXPIRED

SellerEvidenceState = UNCLAIMED | CLAIM_PENDING | CLAIM_DENIED |
  SELLER_DRAFT | VALIDATION_CONFLICT | IN_REVIEW | CHANGES_REQUESTED |
  PUBLISH_READY | PUBLISHED | SUPERSEDED | PUBLICATION_FAILED

SellerReviewDecision = REQUEST_CHANGES | APPROVE | REJECT

SellerExportFormat = JSON | HTML | REUSABLE_ANSWER

ResultArtifactType = DECISION_RECORD | CONFIGURATION_CHANGE |
  CONTRACT_CONFIRMATION | CANCELLATION_CONFIRMATION |
  ORDER | ENTITLEMENT | MIGRATION_RECORD | STACK_PATCH |
  OUTCOME_CHECKPOINT
```

### 8.1 Seller UI projection

The narrow seller route uses a separate role-filtered projection:

```json
{
  "product": {
    "id": "product_fixture_d",
    "name": "Fixture D",
    "seller_state": "SELLER_DRAFT",
    "current_version": 3,
    "href": "/seller/product-evidence/product_fixture_d"
  },
  "actor": {
    "role": "SELLER_EDITOR",
    "capabilities": ["VIEW_OWN_DRAFT", "EDIT_CLAIMS", "ADD_EVIDENCE", "SUBMIT_REVIEW"]
  },
  "publisher_authority": {
    "value": "PLATFORM_COMPILED",
    "label": "Compiled by Seilnsara",
    "supporting_copy": "Publisher authority identifies who stands behind this package; it does not mean every claim was independently verified."
  },
  "pack_health": {
    "status": "NEEDS_ATTENTION",
    "required_claim_count": 12,
    "complete_claim_count": 9,
    "stale_claim_count": 1,
    "conflict_count": 1
  },
  "validation": {
    "status": "HAS_GAPS",
    "gaps": [{
      "id": "gap_retention",
      "field": "data_retention_days",
      "safe_message": "Add a current retention value and supporting evidence.",
      "href": "/seller/product-evidence/product_fixture_d?field=data_retention_days"
    }]
  },
  "review": null,
  "reusable_answers": {
    "published_version": 2,
    "published_answer_count": 18,
    "formats": ["JSON", "HTML", "REUSABLE_ANSWER"],
    "href": "/v1/seller/pack-versions/pack_fixture_d_v2/exports"
  },
  "activity_metrics": {
    "window_start": "2026-07-01T00:00:00Z",
    "window_end": "2026-08-01T00:00:00Z",
    "answer_rendered_count": 42,
    "seller_handoff_requested_count": 7,
    "observed_self_service_count": 35,
    "href": "/v1/seller/products/product_fixture_d/activity-metrics"
  },
  "available_actions": [{
    "id": "SUBMIT_REVIEW",
    "label": "Submit for review",
    "method": "POST",
    "href": "/v1/seller/pack-drafts/draft_fixture_d/submit-review",
    "requires_confirmation": true
  }],
  "version_links": {
    "current": "/seller/product-evidence/product_fixture_d/versions/3",
    "previous": "/seller/product-evidence/product_fixture_d/versions/2"
  }
}
```

Entry is through a signed product invitation or claim-product search, followed by the stable `/seller/product-evidence/{product_id}` route. `UNCLAIMED` offers claim; `CLAIM_PENDING` preserves submitted authority proof; `CLAIM_DENIED` explains the safe reason and permits different proof; `SELLER_DRAFT` autosaves; `VALIDATION_CONFLICT` links errors to fields; `IN_REVIEW` freezes the revision; `CHANGES_REQUESTED` links reviewer comments; `PUBLISH_READY` exposes publish only to an authorized seller reviewer; `PUBLISHED` is immutable and can spawn a new version; `SUPERSEDED` is read-only; `PUBLICATION_FAILED` exposes only a server-authorized retry/escalation. Unauthorized private fields and controls are absent from the payload.

Exports contain only fields from an immutable published Pack version and carry Pack ID/version, publisher authority, claim-verification summary, generated time, and content hash. `REUSABLE_ANSWER` renders the seller-approved answer plus source links; it cannot add generated claims. `observed_self_service_count` is an observational event count, not claimed labor savings: count one published-answer render per tenant/session/question fingerprint within 24 hours only when no seller handoff event follows in that session. Display the measurement window and handoff count beside it; never call the metric causal "deflection" without a validated baseline.

## 9. Required API surface for the first build

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Runtime health |
| `POST` | `/v1/demo/reset` | Development/test-only deterministic fixture reset |
| `GET` | `/v1/decision-requests` | Role-filtered Decisions index with active/history rows, current stage, blocker, checkpoint, deadline, and version link |
| `POST` | `/v1/decision-requests` | Create an action-neutral decision request |
| `GET` | `/v1/decision-requests/{id}` | Request/workflow summary |
| `POST` | `/v1/decision-requests/{id}/discover` | Run governed comparison |
| `GET` | `/v1/decision-requests/{id}/decision-view` | Complete UI projection above |
| `GET` | `/v1/decision-requests/{id}/decision-rules` | Buyer-authorized gates, preferences, and versions |
| `GET` | `/v1/requirement-briefs/{id}` | Role-filtered sanitized seller view |
| `POST` | `/v1/decision-requests/{id}/calibration-runs` | Run known options through the Calibration check |
| `POST` | `/v1/decision-requests/{id}/solution-options/{solution_plan_id}/actions` | Keep/eliminate/ask-vendor/save/evidence feedback on an action plan |
| `POST` | `/v1/engagements/{id}/consent` | Record scoped mutual-consent decision |
| `GET` | `/v1/decisions/{id}` | Decision Ledger and exact versions |
| `GET` | `/v1/decisions/{id}/counterfactuals` | Verified generic/private-fact and recovery reruns |
| `POST` | `/v1/decisions/{id}/simulations` | Non-authoritative weight/fact sensitivity rerun that creates a new simulation record |
| `POST` | `/v1/evaluation-runs/{id}/replay` | Replay frozen inputs and compare decision hashes |
| `POST` | `/v1/decision-rules/{id}/proposals/{proposal_id}/accept` | Accept an authorized calibration/feedback proposal and create a new rules version |
| `POST` | `/v1/decision-rules/{id}/proposals/{proposal_id}/reject` | Reject a proposal with zero ranking effect |
| `POST` | `/v1/decisions/{id}/plan-selections` | Idempotently bind a selectable Solution Plan to source version/hash and create the immutable selected Decision version |
| `POST` | `/v1/decisions/{id}/action-runs` | Start the single server-authorized action-neutral execution path; payment is only one possible substep |
| `GET` | `/v1/action-runs/{id}` | Read checkpoint, owner, blocking task, recovery action, and verified result artifacts |
| `GET` | `/v1/seller/products/search` | Seller-safe provisional product search with public fields only |
| `POST` | `/v1/seller/products/{product_id}/claim` | Start authorized vendor claim of an existing provisional product |
| `GET` | `/v1/seller/products/{product_id}/view` | Read the seller UI projection, claim/review state, Pack health, safe gaps, actions, and versions |
| `GET` | `/v1/seller/pack-drafts/{id}` | Read the seller-authorized Product Evidence draft, validation gaps, and version |
| `PATCH` | `/v1/seller/pack-drafts/{id}` | Correct typed Product Evidence, fit/anti-fit, and publication fields |
| `POST` | `/v1/seller/pack-drafts/{id}/evidence` | Attach evidence metadata/source reference without accepting it as verified by default |
| `POST` | `/v1/seller/pack-drafts/{id}/submit-review` | Freeze a draft revision for validation/reviewer approval |
| `POST` | `/v1/seller/pack-drafts/{id}/review-decisions` | Append an immutable request-changes/approve/reject event with actor, reason, revision hash, and idempotency key |
| `POST` | `/v1/seller/pack-drafts/{id}/publish` | Publish an authorized immutable Pack version after validation and approval |
| `POST` | `/v1/seller/pack-versions/{id}/suspend` | Authorized safety suspension with immutable reason/effective time; never delete history |
| `GET` | `/v1/seller/pack-versions/{id}/exports` | Hash-bound JSON/HTML/reusable-answer exports containing published fields only |
| `GET` | `/v1/seller/products/{product_id}/activity-metrics` | Windowed answer-render/handoff/self-service observations with non-causal labels |
| `POST` | `/v1/decisions/{id}/purchase-intents` | Lock selected quote/action |
| `POST` | `/v1/purchase-intents/{id}/approval-requests` | Start approval |
| `POST` | `/v1/approval-requests/{id}/approve` | Authenticated exact-hash approval |
| `POST` | `/v1/approval-requests/{id}/reject` | Authenticated rejection with safe reason and immutable event |
| `POST` | `/v1/purchase-intents/{id}/prava-sessions` | Create hosted Prava session |
| `GET` | `/v1/purchase-intents/{id}/status` | Reconciled payment/fulfillment state |
| `GET` | `/v1/purchases/{id}/receipt` | Decision-linked receipt |
| `GET` | `/v1/organizations/{id}/stackfile` | Current and proposed stack views |

Long operations return `202` with `workflow_id`, `status_url`, and `events_url`. The UI may initially poll `status_url`; SSE can follow without changing domain semantics. The decision view's `active_operation` contains operation kind, status, last successful checkpoint, started/updated timestamps, owner, retryability, and whether leaving the page is safe. Refresh/re-entry restores this object. While an external side effect is `UNCERTAIN`, the server omits duplicate action descriptors and the UI cannot manufacture a retry.

## 10. Demo fixture

Check in deterministic, fictional data under `fixtures/demo/`:

- `buyer_passport.json`: private policy, stakeholders, budget/authority, operational preferences;
- `stackfile.yaml` and `stackfile.lock.json`;
- `contract.json`, `renewal_event.json`, and safe usage/outcome observations for the incumbent meeting-intelligence instance;
- `purchase_brief.json` and its sanitized `requirement_brief.json`;
- one private `product_passport.json` per fictional seller, with publication tests proving private fields do not enter Packs;
- four SEIL Pack JSON files representing buyer rejection, seller pass, incumbent runner-up, and replacement winner;
- evidence metadata and safe sample snippets;
- indicative offers and one live-quote fixture;
- expected Decision Ledger, Stackfile patch, approval payload, receipt, and entitlement.

Fixture tests must prove:

1. Removing private context changes the selected action to the cheapest replacement option.
2. Adding private context produces one `SIRA_INELIGIBLE`.
3. Published seller rules produce one `SEIL_PASS` without buyer-private disclosure.
4. The winner and runner-up order are deterministic.
5. Seller positioning cannot change that order.
6. Calibration feedback creates a new Purchase Brief proposal/version rather than silently changing the existing result.
7. The seller-visible Requirement Brief contains no hidden buyer identity, budget, contacts, private failures, or unrestricted Stackfile fields.
8. `ASK_VENDOR` in `SELECTIVE` mode reveals no contact details until the scoped engagement consent completes.
9. Duplicate aliases, editions, resellers, or offers cannot increase option count, coverage, display frequency, or rank.
10. Unknown optional evidence cannot improve conservative rank; its optimistic bound and evidence frontier are visible.
11. Rank instability is detected when another option's optimistic ordering can beat the selected option's conservative ordering.
12. Generic and decisive-private-fact counterfactuals are discovered by rerun and reproduce their stored before/after evaluation-payload hashes.
13. Current-stack `REUSE_EXISTING`, `CONFIGURE_EXISTING`, and `NO_ACTION` plans are considered even when no seller Pack proposes them; the renewal fixture also produces `RENEW`, `RESIZE`, and `CANCEL`.
14. Input permutation and proportionally equivalent preference weights do not change final order.
15. Frozen engine, pipeline, taxonomy, normalization, evidence, Pack, Company Profile, and Stackfile versions replay to the same canonical decision payload and hash.
16. A record that is both unavailable and stale retains both reasons and always chooses `UNAVAILABLE` as its primary status; every precedence combination is covered.
17. Score bounds aggregate on complete Solution Plans, decision stability is top-level, and ordering-frontier, resolution-frontier, and quote-policy membership are independently correct.
18. Exact numerator/denominator comparison determines rank; two display-rounded equal values cannot create a false tie.
19. Counterfactual search freezes every non-ablated version, uses stable cardinality/ID tie-breaks, and returns `NO_SMALL_COUNTERFACTUAL_FOUND` when the v1 search limit is exhausted.
20. A missing taxonomy/aggregation bound produces `UNDETERMINED` robustness and blocks autonomous execution.
21. The incumbent contract, cancellation deadline, current usage/outcome, renewal quote, and replacement cost produce a reproducible renew/resize/configure/no-action/replace/cancel action set.
22. Category synonyms and approved query expansion recall every known fixture, while retrieval similarity and irrelevant recalled records have zero effect on eligibility or final ordering.
23. Stack-risk, TCO, weighted decision-material coverage, and evidence-age interval formulas reproduce exact lower/base/upper values for single- and multi-component plans.
24. Counterfactual records contain evaluation-payload hashes rather than the enclosing decision hash; final decision hashing is deterministic and non-circular.
25. Platform-compiled and external-unsealed packages project as `RESEARCH_ONLY`, never produce `SEIL_PASS`, never enter executable ordering, and expose no Purchase Intent or execution action.
26. Each executable first-build `SolutionActionType` follows its declared execution path and produces the required verified Result artifacts; zero-charge actions create no Purchase Intent, Prava session, fee, payment, or decorative receipt. `CONSOLIDATE` renders the frozen schema fixture with no selection/execution action.
27. Decisions-index, stable stage/version URLs, refresh, reconnect, and browser Back restore the same server-owned stage/checkpoint without mutating or silently discarding persisted state.
28. Every `SellerEvidenceState` renders its permitted controls and recovery; claim denial/publication failure preserve data, and only an authorized seller reviewer can publish.
29. Requester, decision-maker, policy reviewer, budget owner, cardholder, implementer/IT operations, auditor, seller editor, and seller reviewer payload snapshots omit every unauthorized fact, task, route, and control rather than marking it disabled.
30. `buyer_txn_demo_v1` is an exact USD 2.00 line item included once in a charge-bearing option TCO, Purchase Intent, approval amount, and receipt; it is absent on retries and zero-charge actions, labelled demo-only, and seller-paid commission fixtures are rejected.
31. Selecting the same plan twice with one idempotency key returns one selected Decision version; selecting a different plan creates a new version and supersedes the old Purchase Intent/approval/action state.
32. Every `execution_steps` fixture supplies a closed type/status, owner, timestamps, checkpoint/artifact, blocker, and at most one authorized action; the UI renders the same sequence without inference.
33. The exact `1/2` no-history prior contributes to criterion satisfaction but zero evidence coverage and no hard-gate pass; prior policy/version/hash replay deterministically.
34. Stack-risk lower/base/upper tiers reproduce from declared `risk_rule_set` IDs and normalized inputs; incomplete input coverage returns `BOUND_UNAVAILABLE` instead of low risk.
35. Seller search, review decision, publish/suspend, export, and activity-metric fixtures preserve unpublished/buyer-private denial and reproduce export content hashes.
36. `observed_self_service_count` deduplicates by tenant/session/question/24-hour window, excludes sessions with a seller handoff, and is never labelled causal savings or proven deflection.

## 11. UI screens owned by the laptop

### 11.1 Information architecture and stage hierarchy

Build one chat-first **SIRA workspace** with an embedded **Decision Canvas** containing five persistent stages:

1. **Need** — upcoming meeting-intelligence renewal, incumbent/contract/deadline, desired outcome, users/owner/payer, and only decision-changing clarification.
2. **Company fit** — decisive Company Profile and current-stack facts, provenance/freshness, private-versus-shared boundary, Purchase Brief gates, visibility, disclosure preview, and Calibration check.
3. **Options** — recommendation and plain-language stability summary; aligned action-neutral rows showing support status, comparable cost, Stack change, and next action. Raw scores, risk, evidence coverage/frontier, provenance, and calculations live in the ledger drawer. Ask-vendor and comparison feedback happen here.
4. **Action** — the selected Action Plan's server-provided sequence: **Review -> Required authority -> Execute or assign -> Verify**. Payment and merchant fulfillment appear only when applicable. Show one current substep, one primary action, completed/next substeps, owner, and last checkpoint.
5. **Result** — action-specific verified artifacts, Company-stack consequence, remaining work, owner, and outcome checkpoint. Show a receipt only when money moved.

SIRA chat is the primary creation surface. Build a minimal **Decisions** index for re-entry: an **Active** list ordered by nearest decision/cancellation deadline and read-only **History** grouped by current/superseded version. Each row shows outcome, incumbent/category, owner, deadline, stage, blocker/next action, last checkpoint, and version. A structured request opens Need in the Decision Canvas; resume opens the server-owned current stage with its attached conversation.

Use stable UI routes: `/decisions`, `/decisions/new`, and `/decisions/{request_id}/versions/{decision_version}/{need|company-fit|options|action|result}`. Stage navigation pushes browser history. Back closes an open drawer/sheet first, then returns to the prior stage/index; it never mutates data. Warn before abandoning a dirty unsubmitted form. A superseded URL remains read-only and links to current instead of silently redirecting.

Also build one narrow `/seller/product-evidence/{product_id}` route driven by Section 8.1 for claim/status, Pack health, stale evidence, typed correction, evidence, fit/anti-fit, review, reusable answer/export, and publication. Do not build a second chat product or full seller dashboard.

The first-build buyer navigation contains the SIRA conversation workspace, **Decisions**, the active Decision Canvas, and the account menu. Company Profile facts, Stack context, approvals, and tasks appear contextually inside the current decision. Do not render disabled or empty destinations. The seller route appears only for an authorized seller role.

#### 11.1.1 Action-neutral completion contract

| Action | Action-stage path | Required Result proof |
|---|---|---|
| `REUSE_EXISTING` | review retained capability -> owner confirms -> record | decision record, unchanged Company stack, predicted saving, next outcome/review date |
| `CONFIGURE_EXISTING` | review configuration patch -> required approval -> execute/assign -> verify | configuration-change record, verification evidence, staged/active Stack update, checkpoint |
| `NO_ACTION` | record reason/owner -> set next review | no-action Decision record, unchanged Stack, next review trigger |
| `RENEW` / `RESIZE` | review contract/quantity/quote -> approve -> pay only if immediately charged -> verify | renewal/amendment confirmation, term/quantity, receipt when charged, contract/Stack update |
| `CANCEL` | review dependency-safe exit/data plan -> approve -> submit -> verify | cancellation confirmation/effective date, export/retention/revocation proof, staged removal, checkpoint |
| `BUY` / `REPLACE` | review acquisition/migration -> approve -> pay when charged -> provision -> verify deployment/retirement | order/receipt when charged, entitlement, migration/deployment state, staged then active Stack patch |
| `CONSOLIDATE` | **first-build schema/render fixture only**; show the dependency-ordered review/execute/reconcile sequence but expose no start action | frozen per-component completion/compensation specimen, final Stack diff, and conditional receipt specimen; construction and execution are deferred by Section 14 |

Zero-charge actions skip Purchase Intent, Prava, payment states, and transaction fee. A workflow completion flag alone never qualifies as Result proof. In the first build, `CONSOLIDATE` proves contract and responsive rendering only; the API omits its selection/execution action and returns no false executable state.

### 11.2 Visual system

The implementation default is **operational cartography**, intentionally distinct from a warm editorial marketplace:

| Token | Value |
|---|---|
| Canvas | `#F3F6F5` |
| Surface | `#FFFFFF` |
| Surface subdued | `#E9EFEC` |
| Ink | `#13201C` |
| Text muted | `#52615B` |
| Border | `#CBD6D1` |
| SIRA accent / hover | `#006B5F` / `#005348` |
| Focus | `#1D4ED8` |
| Success / background | `#157347` / `#E7F4EC` |
| Warning / background | `#8A5A00` / `#FFF4D6` |
| Danger / background | `#B42318` / `#FDECEA` |
| Info / background | `#2E5AAC` / `#EAF0FF` |

- **Type:** vendored Geist Sans for UI/headings with `system-ui, Segoe UI, sans-serif` fallback; `ui-monospace` for IDs, versions, timestamps, and provenance. No runtime font request.
- **Scale:** page title 32/38, section title 22/28, body 15/22, comparison text 14/20, metadata 12/16.
- **Spacing:** 4-pixel base; normal gaps 8/12/16/24/32; comparison row minimum 56 pixels.
- **Shape:** 6-pixel controls, 10-pixel panels, full pills only for statuses; borders carry hierarchy and shadows are reserved for the overlay drawer/sheet.
- **Layout:** 216-pixel desktop rail, work canvas up to 1280 pixels, evidence drawer 420 pixels; use tabular numerals for money and score detail.
- **Focus/motion:** 2-pixel focus ring plus 2-pixel offset; 120–180 ms state transitions; zero nonessential motion under reduced-motion.
- **Iconography:** simple 16/20-pixel line icons paired with text; no icons in decorative colored squares.

Never use beige editorial styling, gradients, glass effects, anthropomorphic SIRA/SEIL avatars, generic KPI-card grids, confetti-led success, or a prominent fit percentage.

### 11.3 Signature components

1. **Decision Path:** compact five-stage progress/navigation strip with current state, blocker, version, and last checkpoint.
2. **Option Matrix:** native semantic table on desktop. Default columns are action/support status, comparable cost, Stack change, and next action. The selected recommendation is pinned but alternatives remain visible.
3. **Decision Ledger drawer:** four ordered sections—**Why this action** (default open), **Evidence**, **What could change**, and **Audit & math**. Option-row links deep-link to the relevant section; close restores focus to the invoking control. Exact rational bounds, criterion math, evidence age, provenance, coverage/frontier, counterfactual, and versions never leak into the default row.
4. **Evidence Mark:** publisher authority shown separately from claim verification/freshness: `SELLER_SEALED` = **Published by vendor**, `PLATFORM_COMPILED` = **Compiled by Seilnsara**, and `EXTERNAL_UNSEALED` = **External, not claimed**. Always show: **“Publisher authority identifies who stands behind this package; it does not mean every claim was independently verified.”**
5. **Stack Diff:** compact before/after strip for added, removed, retained, staged, and dependency-changed items; no free-form graph in v1.
6. **Execution Timeline:** Review, required authority, execution/assignment, verification, and Company-stack state with one current substep and one primary action. Payment and merchant fulfillment are conditional branches, not permanent steps.

If a material input changes, show a persistent **Decision updated** banner, decisive before/after diff, superseded approval/payment state, and one **Review new version** action. The old version remains read-only and linkable.

### 11.4 State and recovery matrix

| Stage | Preserve on waiting/error | Blocking/empty treatment | Primary recovery |
|---|---|---|---|
| Need | entered request and validated fields | explain the missing decision-changing input and owner | provide/correct the named input |
| Company fit | confirmed facts, sources, and sharing preview | show conflict/stale fact, impacted rule, and authorized resolver | resolve fact or continue only when server permits |
| Options | last complete option matrix and coverage statement | partial results identify whether more evidence can change rank; no eligible action uses its dedicated result | request named evidence, change requirement, or choose allowed alternative |
| Action | exact selected plan, applicable amount/authority, and completed substeps | omit unsafe next actions; show side-effect state, owner, and expiry | complete the single server-authorized next step |
| Result | action-specific artifacts, payment/order facts when applicable, and Stack consequence | never collapse charged-but-unfulfilled or partially completed into a generic failure | complete, compensate, retry, escalate, refund, or close only as server permits |

Required exception states:

| State | Required UI behavior |
|---|---|
| Consent declined | retain comparison; reveal no contacts; offer continue privately or choose another option |
| Quote/approval expired | retain old values read-only; disable payment; refresh quote and review the changed version |
| Payment declined | state that no successful charge was confirmed; allow only server-authorized retry/change path |
| Payment uncertain | show last provider checkpoint/time; disable duplicate payment; reconcile or escalate |
| Paid-unfulfilled | state confirmed payment separately from missing entitlement; expose provisioning retry/support/refund path |
| Decision superseded | persistent banner, decisive diff, invalidated authority, and Review new version |
| No eligible supported action | show coverage/exclusions, exact blockers, evidence/category limits, and safe next actions; never a generic empty state |
| Research only | label authority and uncertainty; omit select/execute; offer vendor claim/publication, normalization, or a supported alternative |
| Rank unstable | show “Could change if…” plus the named evidence frontier; Action is unreachable unless the server exposes a policy-authorized exception |
| Rank undetermined | show the missing bound and owner; omit every execution control until repair and reevaluation |
| Authority required | name the required role without leaking restricted facts; omit approval/execution for the current actor; assign/request owner |
| Approval rejected | keep the rejected version read-only with safe reason/role/time; omit payment; close or revise into a new version |
| Partial fulfillment | separate paid/ordered facts from every missing item; never apply the full Stack patch; expose only per-item server-authorized recovery |

Long operations persist in the backend projection. Refresh, reconnect, and returning later restore `active_operation`, latest successful checkpoint, timestamp, and current owner. Unknown side effects disable duplicate primary actions until reconciliation resolves them.

Seller recovery uses the same preservation rule:

| Seller state | Required UI/recovery |
|---|---|
| `UNCLAIMED` | public-safe summary plus **Claim this product**; no editor |
| `CLAIM_PENDING` | submitted authority proof and review status; update/withdraw only when returned by the API |
| `CLAIM_DENIED` | safe denial reason and **Submit different proof**; package remains intact |
| `SELLER_DRAFT` | autosave, Pack health, validation gaps, stale-evidence queue |
| `VALIDATION_CONFLICT` | error summary plus field links and **Resolve issues** |
| `IN_REVIEW` | frozen revision, reviewer/owner, submitted time, permitted withdraw |
| `CHANGES_REQUESTED` | grouped comments linked to fields and **Create revised draft** |
| `PUBLISH_READY` | immutable preview; **Publish version** only for authorized reviewer |
| `PUBLISHED` | immutable current Pack, health/export, and **Create new version** |
| `SUPERSEDED` | read-only history with current-version link |
| `PUBLICATION_FAILED` | last checkpoint/failure class and only server-authorized retry/escalation |

### 11.5 Responsive and accessibility contract

- **Desktop (`>=1024px`):** compact rail, dominant canvas, optional 420-pixel right drawer; Option Matrix is a native table and row actions are ordinary buttons/links, not an ARIA grid.
- **Tablet (`640–1023px`):** rail collapses; drawer overlays; comparison fields remain aligned.
- **Mobile (`<=639px`):** one-option summary plus a tray of up to three options per Decision version. Add/remove selection persists through stage navigation, resets visibly on supersession, and opens an attribute-by-attribute vertical comparison with a sticky labelled option switcher. Evidence is a full-screen sheet. At 320 CSS pixels there is no page-level horizontal scroll and no desktop table is squeezed below readability.
- All stages reflow at 200% and 400% browser zoom. In Windows forced-colors/high-contrast mode, text, borders, focus, status, selected state, and errors remain perceivable without background color.
- Maintain a logical heading/focus order, trap and restore focus for drawer/sheet, announce operation/validation/supersession changes through scoped live regions, place an error summary before invalid fields, use 44-by-44-pixel touch targets, meet WCAG 2.2 AA contrast, respect reduced motion, and never encode status by color alone.
- Run automated axe checks on every fixture state. Manually test keyboard plus NVDA for the Decision Path, Option Matrix, Decision Ledger drawer/full-screen sheet, mobile comparison tray, form error summary, approval rejection, uncertain payment, and partial-fulfillment recovery.

### 11.6 Role-aware presentation

| Role | Visible scope | Permitted first-build controls |
|---|---|---|
| Requester/end user | own request fields, safe progress, assigned clarification, final safe result | create/edit before lock, answer assigned questions, outcome feedback |
| Decision-maker | Decision rules, allowed Company facts, Action Plans, stability/counterfactual, Stack impact | keep/eliminate/ask vendor, select plan, accept a permitted decision exception |
| Policy reviewer | assigned policy domain, supporting evidence, impacted gate, expiry | approve/reject/request evidence/grant policy-defined exception |
| Budget owner/procurement | comparable TCO including SIRA fee, quote/terms, cost center, approval history | approve/reject exact amount and terms, request revised quote |
| Cardholder | approved merchant, line items, amount/currency/fee, expiry, Prava/payment state | authorize exact payment or exit; no decision editing |
| Implementer/IT operations | assigned configuration, dependency, migration, deployment, fulfillment, and Stack verification detail | execute or acknowledge assigned steps, attach verification, report blocker, verify fulfillment/Stack state; no commercial approval |
| Auditor | authorized immutable versions, evidence lineage, action/approval/payment/fulfillment history | read/export only |
| Seller editor | own claimed drafts, health, gaps, stale evidence, comments | edit/evidence/submit; cannot approve own high-risk publication |
| Seller reviewer | own frozen revision, validation report, diff, publication authority | request changes, approve, publish, suspend when authorized |

Filter every projection server-side by tenant, role, purpose, and object. Out-of-scope facts, counts, tasks, routes, and controls are absent from payload, DOM, accessible tree, analytics, and notifications—not disabled or hidden client-side.

### 11.7 Interface terminology

| Internal/API concept | Primary interface language |
|---|---|
| Buyer Passport | Company Profile |
| SEIL Pack | Product Evidence |
| Purchase Brief | Decision rules |
| Solution Plan | Action plan |
| Stackfile | Company stack |
| Stackfile patch | What changes in your stack |
| Counterfactual | What changed the recommendation |
| Rank stability: `STABLE` | Stable across current uncertainty |
| Rank stability: `UNSTABLE` | Could change if… |
| Rank stability: `UNDETERMINED` | Not yet determined |
| Evidence frontier | What information could change this decision |
| Conservative/optimistic score bounds | Supported range (drawer only) |
| Calibration check | Test the decision rules |
| Purchase Intent | Approval details |
| `SELLER_SEALED` | Published by vendor |
| `PLATFORM_COMPILED` | Compiled by Seilnsara |
| `EXTERNAL_UNSEALED` | External, not claimed |
| `ADVISORY_ONLY` / `RESEARCH_ONLY` | Research only |

All stages work without chat. The UI may reveal canonical terms in the ledger drawer for audit, but primary headings/actions use the language above.

## 12. Implementation sequence

```text
Repository + contracts + fixtures
        |-----------------------> Laptop builds UI against fixtures
        v
Domain + SIRA Decision Graph + Stackfile
        |-- recall/dedup + evidence assessment
        |-- gates + Solution Plan builder
        |-- score bounds + ordering + counterfactual
        v
FastAPI + persistence + approval
        v
Senso + Prava + merchant/fulfillment adapters
        v
Generated client + real API wiring
        v
Cross-branch integration + E2E proof
```

**Contract conformance gate:** much of this route and schema surface now exists. Treat the frozen OpenAPI and closed JSON Schemas as current truth. Any remaining legacy caller-supplied preference/plan/counterfactual fields or candidate-oriented aliases are compatibility-only and must not become authoritative. For every contract change:

1. keep raw frozen facts/rules/evidence as the only authoritative Decision Graph inputs;
2. update closed JSON Schemas and OpenAPI first;
3. regenerate the TypeScript client and frozen fixtures;
4. update producers, consumers, and the Section 10 contract suite together.

## 13. Definition of done for the first integrated build

1. Fresh setup instructions work on both computers without committed secrets.
2. Backend unit tests reproduce the four component qualification states, generated current-stack actions, and selected plan.
3. OpenAPI generation and TypeScript client generation are repeatable.
4. Web UI renders chat intake and every Decision Canvas stage and required interaction state from fixture and real API modes.
5. Buyer-private fields are absent from the seller-facing brief and UI network payloads not authorized for the current role.
6. Private Product Passport fields excluded from the Pack cannot appear in buyer APIs, seller positioning, prompts, traces, or fixtures intended for buyers.
7. Solution-option feedback and calibration changes create explicit versions; an unaccepted proposal has zero ranking effect.
8. Selective engagement reveals no party's contact details until scoped mutual consent is recorded.
9. Approval changes to `SUPERSEDED` after any material Purchase Intent mutation.
10. Duplicate execution requests cannot create a second merchant order or entitlement.
11. A real supported Prava sandbox authorization reaches a genuine merchant/processor sandbox path.
12. Merchant result is reported/reconciled and expected entitlement is verified.
13. Receipt links request, decision, Pack/offer/quote versions, approval, Prava references, merchant order, amount, and entitlement.
14. The Stackfile proposed/staged change is visible and not falsely marked as active deployment.
15. Playwright demonstrates the complete request-to-receipt path plus consent decline, payment decline, and uncertain-payment recovery views.
16. The Decision Graph computes criterion satisfaction, evidence assessments, plan dimensions, score bounds, rank stability, and counterfactuals from raw frozen fixture inputs; callers do not inject authoritative precomputed fit or decisive facts.
17. Recall/deduplication records included, excluded, and merged identities; duplicate supply has zero effect on order and apparent coverage.
18. Unknown evidence never improves conservative rank, every unstable rank exposes its evidence frontier, and unstable decisions cannot auto-execute.
19. Replay of a frozen evaluation produces the same canonical ordering, primary status, counterfactual payload, and decision hash; generated IDs/timestamps may differ.
20. The buyer UI uses procurement-native labels, a chat-first workspace, one embedded five-stage Decision Canvas, aligned option comparison, and separate fit/risk/cost/evidence/stability dimensions.
21. The narrow seller Product Evidence flow can claim, correct, evidence, review, and publish without exposing buyer-private data.
22. Playwright covers desktop and mobile paths plus loading, empty, partial, blocked, expiry, decline, uncertain, paid-unfulfilled, and verified-success states without requiring chat.
23. The backend-owned view supplies current stage, actor role/capabilities, available action descriptors, blockers, active operation, and version/supersession state; the frontend never infers authority.
24. One action-neutral option contract renders buy, renew, resize, replace, reuse, configure, cancel, consolidate, and no-action plans; `CONSOLIDATE` is visibly non-executable fixture data in the first build, and `NO_ELIGIBLE_SUPPORTED_ACTION` renders a dedicated covered result.
25. Material mutation produces the Decision-updated banner, decisive diff, read-only prior version, and invalidated approval/payment state.
26. The exact visual tokens and six signature components in Section 11 render consistently without a generic card dashboard or prominent numeric fit score.
27. The mobile comparison tray preserves up to three options per Decision version and is fully operable with touch, keyboard, and screen reader.
28. Refresh/reconnect restores every long-running operation; uncertain side effects cannot expose a duplicate primary action.
29. `/sira`, `/decisions`, and every versioned Decision Canvas URL are stable and linkable; browser Back closes transient UI before navigating stage history, and prior versions remain read-only with a path to the current version.
30. Requester, decision-maker, approver, payer, implementer, and seller views receive only their server-authorized actions and data; unauthorized tasks and commercial details are absent from payloads rather than merely hidden in the interface.
31. The seller Product Evidence surface covers unclaimed, draft, conflicted, incomplete, in review, published, stale, rejected, and superseded states, with a clear owner and recovery action for every nonterminal state.
32. Renew, resize, reuse, configure, cancel, and no-action completions produce their own verified result artifacts without inventing payment, merchant-order, or entitlement states; consolidation completion is render-fixture-only until multi-component execution enters scope.
33. Automated UI checks cover a 320 CSS-pixel viewport, 200% browser zoom, visible keyboard focus, reduced motion, forced-colors mode, automated accessibility scanning, and one screen-reader pass through chat intake and the primary Decision Canvas path.
34. Research-only evidence is unmistakably labelled, publisher authority is kept separate from claim verification, and every buyer-paid transaction fee is itemized in TCO, approval, Purchase Intent, payment, and receipt; it creates no seller/policy boost and affects order only through ordinary disclosed buyer TCO.
35. Plan selection is idempotent, version/hash-bound, and role-authorized; selection creates the immutable selected Decision version, reselection supersedes downstream authority, and zero-charge selection creates no payment state.
36. The Execution Timeline renders every typed step's state, owner, checkpoint, blocker, artifact, and sole authorized action without client-inferred substeps.
37. Stack-risk tiers reproduce from versioned category rule IDs and normalized inputs, and the exact `1/2` v1 neutral outcome prior affects satisfaction but never evidence coverage or a hard gate.
38. Seller claim search, immutable review decisions, publication/suspension, hash-bound reusable exports, and windowed answer/handoff/self-service metrics complete the launch seller-value loop.

## 14. Not part of the first parallel assignment

These remain in the master PRD but must not create cross-laptop conflicts before the integrated path works:

- full enterprise onboarding/SCIM;
- production marketplace onboarding and reputation;
- full seller application, open RFP, and public seller marketplace;
- continuous optimizer and OR-Tools portfolio UI;
- full renewal calendar/automation, mandates, cancellation execution, and cross-tenant learning beyond the locked renewal-decision fixture;
- multi-component/multi-merchant plan construction beyond preserved schema support;
- automated outcome-based ranking or cross-tenant preference learning;
- every software category beyond the locked meeting-intelligence fixture.

Do not delete their abstractions or make schema choices that prevent them. Simply do not implement their full UI/workflows in the first parallel branches.
