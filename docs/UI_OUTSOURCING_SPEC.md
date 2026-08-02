# SIRA + SEIL UI Redesign and Frontend Implementation Specification

**Status:** Outsourcing brief for design and frontend implementation
**Audience:** Product designer, UX designer, frontend engineer, QA engineer, and delivery lead
**Product owner:** SIRA + SEIL team
**Last verified against the repository:** 2026-08-02
**Contract version:** 1.0

## 1. The assignment

Re-design and rebuild the SIRA + SEIL web interface so it is clear, calm, attractive, and useful for real work.

The existing web UI is a disposable functional prototype. **Do not use its visual hierarchy, page layouts, component boundaries, card density, copy volume, colors, or styling as the design reference.** It over-explains the system and does not provide a good product experience.

Reuse only:

- the product concepts and language described in this document;
- the generated API contract and types;
- the privacy, authority, concurrency, and state-transition rules;
- useful fixture data for development and testing; and
- the underlying backend behavior that is explicitly marked as available today.

The contractor is expected to produce an original visual direction and a production-quality frontend, not a cosmetic reskin of the current screens.

### 1.1 Desired experience

The product should feel like a confident, modern decision and procurement workspace:

- one clear job and one clear next step per page;
- progressive disclosure instead of showing every system detail at once;
- concise, human language with deeper evidence available on demand;
- a comparison experience that is genuinely easy to scan;
- clear separation between facts, recommendations, approvals, payments, fulfillment, and outcomes;
- calm handling of long-running work, blockers, stale data, and recovery;
- no fake chat interface and no dashboard made from dozens of equal-weight cards;
- no local guesswork about what the user is allowed to do; and
- no buyer-private information leaking into seller pages.

The exact visual identity, typography, color system, spacing system, illustration style, and desktop layout are part of the redesign assignment. The current `DESIGN.md` remains useful for product semantics and security invariants, but its visual treatment is **not mandatory** for this engagement.

## 2. Source of truth

When sources disagree, use this order:

1. [`contracts/openapi/openapi.json`](../contracts/openapi/openapi.json) for the public HTTP contract.
2. [`packages/api-client/src/types.ts`](../packages/api-client/src/types.ts) and [`packages/api-client/src/client.ts`](../packages/api-client/src/client.ts) for generated frontend types and operations.
3. [`docs/BUILD_SPEC.md`](BUILD_SPEC.md) for the first-build execution contract.
4. [`docs/PRD.md`](PRD.md) for product meaning, privacy boundaries, and longer-term intent.
5. Tested backend implementation and tests for current behavior.
6. [`DESIGN.md`](../DESIGN.md) for semantic and interaction guidance only, not as a visual reference.

The frontend must use the generated `@sira/api-client`. It must not maintain hand-written copies of API response types.

## 3. Product model

SIRA + SEIL is a pair of B2B commerce agents that help companies buy and sell products and services. It is not positioned as a “control plane.” The current repository focuses on B2B software commerce.

### 3.1 SIRA: the buying agent and buyer workspace

SIRA works for the buyer. It helps a company move from a need to the best supported action for that company among the options actually evaluated:

```text
Need -> Company fit -> Options -> Action -> Result
```

The answer is not always “buy a new product.” A valid action may be:

- reuse an existing product;
- configure an existing product;
- take no action;
- buy;
- renew;
- resize;
- replace;
- consolidate; or
- cancel.

SIRA compares options using company policy, stack, contracts, evidence, cost, and private operational facts. It keeps the evaluated decision immutable and auditable.

### 3.2 SEIL: the selling agent and seller workspace

SEIL works for the seller. It helps a B2B company present what it sells, answer buyer questions, prove where the product fits, and move qualified buyers toward a sale. In the current build, this begins with structured, reusable evidence: a seller can claim a product, maintain evidence, obtain independent review, publish a sealed version, export reusable answers, and monitor observational activity.

Seller claims are not automatically buyer-visible or verified. Publisher authority and evidence quality must be shown accurately.

### 3.3 Stackfile

Stackfile is the company’s canonical software dependency graph. It includes the current manifest, lock information, and proposed changes caused by a decision. A proposed change is not the same as an applied change.

### 3.4 Product invariants

These are non-negotiable:

- A conversation or assistant may collect information, but structured versioned records govern the decision.
- Buyer-private and seller-private data never mix.
- A company policy block is different from a seller saying a product is unsupported.
- Selection, approval, payment, fulfillment, deployment, and outcome are separate events.
- A selected option is bound to an exact decision version and SHA-256 hash.
- Approval is bound to an exact purchase-intent hash.
- Seller edits are bound to a draft revision and exact revision hash.
- Server-returned capabilities and action descriptors determine what can be done.
- Unauthorized fields, resource counts, routes, and actions are absent rather than blurred or shown disabled.
- Seller activity metrics are observational, not proof that seller work caused a purchase.

## 4. Roles and authority

The UI should be understandable by role, but it must never derive permissions from a locally stored role name.

### 4.1 Buyer-side roles

- **Requester:** describes the need and follows the decision.
- **Decision-maker / operations owner:** evaluates and selects a supported action.
- **Policy reviewer:** reviews company fit and proposed rule changes.
- **Budget or procurement owner:** creates and manages approval gates.
- **Approver:** approves or rejects the exact purchase intent for a verified role.
- **Cardholder / purchase executor:** starts the controlled checkout.
- **IT operations owner:** executes or verifies deployment and Stackfile changes.
- **Auditor:** reviews immutable records and evidence without taking operational actions.

### 4.2 Seller-side roles

- **Seller editor:** maintains claims, rules, and evidence and submits a draft for review.
- **Seller reviewer:** independently reviews and publishes; cannot approve their own edit/submission where separation is required.
- **Platform operator:** performs allowed platform oversight and recovery work.

### 4.3 Enforcement rules

- Read `workflow.actor.capabilities` and `workflow.available_actions` from the Decision View.
- Read seller `actor.capabilities` and `available_actions` from the Seller Product View.
- Render only authorized actions; do not show a disabled action that reveals inaccessible capability.
- Treat `403` as a real authority boundary, not a UI inconvenience.
- Step-up verification is required for sensitive actions such as plan selection, approval, checkout, seller publication, and suspension.
- Human-only actions cannot be performed by service identities.

## 5. Scope labels

Every screen and feature in this specification uses one of these labels:

| Label | Meaning | Contractor treatment |
|---|---|---|
| **A — API-backed now** | A public, typed backend contract exists and is suitable for a functional UI. | Design, implement, integrate, and test. |
| **B — prototype/static now** | A current page or mock exists, but no complete backend contract supports it. | Design only if included in the agreed deliverables. Never fake persistence in API mode. |
| **C — future scope** | Product intent exists, but the route or backend contract is not part of the current build. | Exclude unless added through a change request. |

## 6. What exists in the current web application

The current application uses Next.js 16, React 19, and TypeScript. It has 15 route patterns plus a shared not-found page. Only the decision and seller areas have meaningful API integration.

| Current route | Current behavior | Status | Redesign instruction |
|---|---|---:|---|
| `/` | Static marketing page. | B | Optional redesign; not part of the core product workflow. |
| `/sign-in` | Development preview with a buyer/seller query switch; no authentication. | B | Do not treat as production auth. Design can be supplied, implementation is blocked by identity work. |
| `/pricing` | Static page. | B | Optional marketing scope. |
| `/security` | Static page. | B | Keep claims factual and reviewed. |
| `/privacy` | Legal placeholder. | B | Content requires legal approval. |
| `/terms` | Legal placeholder. | B | Content requires legal approval. |
| `/home` | Hard-coded identity, workspaces, recent work, tasks, and activation. | B | Do not carry hard-coded content into API mode. |
| `/inbox` | Three hard-coded assignments, including in API mode. | B | No inbox API exists. Exclude from functional acceptance. |
| `/settings/profile` | Hard-coded read-only profile. | B | No profile/settings API exists. |
| `/decisions` | Decision index using API or fixtures. | A | Rebuild completely and retain typed integration. |
| `/decisions/new` | Decision request creation using API or fixtures. | A | Rebuild; correct async and error behavior is required. |
| `/decisions/{requestId}/versions/{version}/{stage}` | Five-stage Decision Room shell. | Mixed A/B | Keep the route concept; rebuild each stage based on actual available data and gaps below. |
| `/seller` | Seller landing/dashboard using seller product data. | Mixed A/B | Rebuild around actionable products, reviews, and evidence health. |
| `/seller/products/search` | Loads products and filters mostly in the browser. | A | Send the supported `q` query to the API. |
| `/seller/product-evidence/{productId}` | Product evidence console with partial lifecycle support. | A | Rebuild and implement the full public seller lifecycle. |
| Not found | Generic safe unavailable page. | A | Preserve safe non-disclosing behavior. |

### 6.1 Current frontend limitations that must not be copied

- Need and much of Company Fit are hard-coded.
- The apparent decision conversation is fake and disabled.
- Several buttons have no handler.
- Options displays only a subset of evaluated plans.
- Some valid option actions are missing.
- Primary selection is inferred from item order instead of server actions.
- The Action page contains demo links and non-functional controls.
- Result artifacts are not currently projected by the backend.
- Invalid stage URLs silently fall back to Options.
- New-decision navigation ignores asynchronous workflow URLs.
- Seller search does not correctly use its server query.
- Seller claim, draft editing, evidence attachment, review, publish, and suspend are incomplete or absent.
- Seller field and version links can lead nowhere.
- There are no frontend unit, component, accessibility, visual-regression, or end-to-end tests.
- There is no centralized offline, reconnect, stale-version, or long-operation recovery experience.

### 6.2 Current frontend integration footprint

The present UI consumes only these ten generated operations:

- list Decision Requests;
- create a Decision Request;
- start Decision Request discovery;
- get the Decision Room;
- record solution-option feedback;
- select an action plan;
- search seller products;
- get a seller product view;
- get a seller pack draft; and
- submit a seller draft for review.

The other public endpoints in section 13 are backend capabilities that a complete frontend still needs to integrate. Their presence in the API must not be confused with an already finished browser flow.

## 7. Target information architecture

### 7.1 Build-now functional routes

These are the recommended functional delivery scope because public API contracts already exist.

```text
/decisions
/decisions/new
/decisions/{requestId}/versions/{version}/need
/decisions/{requestId}/versions/{version}/company-fit
/decisions/{requestId}/versions/{version}/options
/decisions/{requestId}/versions/{version}/action
/decisions/{requestId}/versions/{version}/result
/receipts/{purchaseId}                         optional full-page form; drawer is acceptable
/seller
/seller/products/search
/seller/product-evidence/{productId}
```

The five Decision Room URLs may share one route layout, but each stage needs a distinct page purpose, heading, state model, and primary action. An unknown stage must return a safe 404, not silently render another stage.

### 7.2 Design-only or backend-dependent routes

These can be included in a Figma prototype, but cannot be accepted as fully functional with the current API:

```text
/
/sign-in
/join/{token}
/auth/return
/home
/inbox
/onboarding/sira
/onboarding/seil
/settings/profile
/settings/notifications
/pricing
/security
/privacy
/terms
```

The repository has no sign-up, sign-in, session, invitation, profile, notification, or general task APIs.

### 7.3 Future routes, excluded by default

```text
/evidence/{productId}/versions/{version}
/company-profile
/company-stack
/renewals
/outcomes
/audit
/seller/products
/seller/products/new
/seller/product-evidence/{productId}/versions/{version}
/seller/sources
/seller/opportunities
/seller/opportunities/{id}
/seller/offers/{id}
/seller/activity
/settings/organization
/settings/members
/settings/connectors
/settings/billing
/settings/security
/settings/developer
/settings/audit
/ops/reviews
/ops/trust
/ops/connectors
/ops/taxonomy
/ops/audit
```

Do not invent local data or unsupported endpoints to make these pages appear functional.

## 8. Shared application shell

### 8.1 Navigation

The shell must make the current workspace obvious: buyer/SIRA or seller/SEIL. Recommended primary navigation:

**SIRA**

- Decisions
- Inbox only after an API exists
- Company/Stack only when those pages enter scope

**SEIL**

- Product evidence
- Product search
- Activity only when a supported aggregate page exists

The switcher may be designed now, but it cannot assert a workspace or identity that the server did not authenticate.

### 8.2 Global behavior

- Keep navigation visually quieter than the page task.
- Show actor/workspace identity only from authenticated server context.
- Provide a compact request/support detail that includes the latest `X-Request-Id` after an error.
- Preserve the user’s exact position when a background resource refreshes.
- Do not use global toasts as the only record of important actions. Place durable status near the affected object.
- Use drawers or dialogs for supporting evidence only when deep-linking and keyboard navigation remain reliable.
- On small screens, convert comparison tables into an intentionally designed comparison flow; do not merely allow an unusable wide table to overflow.

## 9. Page-by-page functional requirements

### 9.1 Decision index — `/decisions` — A

**Purpose:** Let a buyer see active work, understand what is blocked, resume the correct step, and review history.

**Primary API:** `GET /v1/decision-requests`

**Required content:**

- Active decisions and history as returned by the server.
- Intent/title, current stage, status, blocker, owner role, last checkpoint, and current decision version where present.
- Server-provided available actions.
- A clear “New decision” action only when authorized.
- Empty state for a workspace with no decisions.
- Loading skeleton, retryable error, permission loss, and stale/background-refresh state.

**Important constraints:**

- The API has no pagination, search, sort, or server-side filters today.
- Modest client-side filtering may be added for the loaded list, but must be labeled and must not imply a complete server search at scale.
- Do not invent task counts or recent work.

### 9.2 New decision — `/decisions/new` — A

**Purpose:** Capture a clear need and create a durable Decision Request.

**Primary API:** `POST /v1/decision-requests`

**Fields:**

| Field | Contract | UX requirement |
|---|---|---|
| `intent` | Required, 10–2000 characters | Plain-language need; show remaining/valid range without noisy counters. |
| `desired_outcome` | Optional, up to 1000 characters | Describe success, not a preferred vendor. |
| `deadline` | Optional | Use a clear date control and timezone-safe serialization. |
| `incumbent_instance_id` | Optional | Do not show until an instance selector/data source exists. |
| `visibility` | `PRIVATE`, `SELECTIVE`, `OPEN_RFP` | Offer Private and Selective. Hide `OPEN_RFP` until marketplace/moderation support exists. |

**Submission flow:**

1. Create one idempotency key for the click.
2. Submit the typed body.
3. Retain that key and identical body if retrying a retryable failure.
4. Use the returned request ID/href instead of constructing assumptions.
5. If discovery is an authorized next action, start it separately.
6. For a `202 WorkflowAccepted`, use `status_url` and `events_url` to show durable progress.
7. Navigate to the current server-reported stage only when the resource is ready.

**Do not:** fake a live assistant, treat an optimistic animation as successful persistence, or silently create an open seller request.

### 9.3 Need — Decision Room stage — Mixed A/B

**Purpose:** Confirm what problem is being solved before evaluating products.

**Available data:** request header and progress from `GET /v1/decision-requests/{requestId}`, plus relevant Decision View fields after discovery.

**Target content:**

- desired outcome;
- deadline;
- incumbent/current approach;
- expected users or team;
- owner, payer, and likely approvers;
- visibility boundary;
- unanswered material questions; and
- a concise checkpoint summary.

**Current limitation:** there is no API to update an existing Decision Request and no complete structured Need-edit contract. In the functional build, show canonical values read-only after creation. Editing is a separately scoped backend requirement.

### 9.4 Company Fit — Decision Room stage — Mixed A/B

**Purpose:** Explain which company facts and rules shape the recommendation without exposing facts the actor cannot see.

**Primary APIs:**

- `GET /v1/decision-requests/{requestId}/decision-view`
- `GET /v1/decision-requests/{requestId}/decision-rules`
- `POST /v1/decision-requests/{requestId}/calibration-runs`
- accept/reject proposal endpoints when a calibration proposes a rule change

**Required content:**

- facts used, including provenance, freshness, and sensitivity labels when supplied;
- `hidden_fact_count` without names or values of hidden facts;
- hard requirements and weighted preferences;
- relevant current-stack context;
- evaluation coverage and data gaps;
- a seller-safe requirement brief preview where the server provides it;
- calibration results and any proposed change; and
- explicit text that a proposal has no ranking effect until accepted.

**Rules:**

- Never infer hidden values from counts, ranking, errors, or seller content.
- Do not display proposals as if already effective.
- Accept/reject must show the reason, step-up requirement, possible new decision version, and supersession outcome.
- A `409` requires canonical reload before another decision.

### 9.5 Options — Decision Room stage — A

**Purpose:** Compare every evaluated action on aligned criteria and choose only a supported exact plan.

**Primary APIs:** Decision View, option feedback, ledger, counterfactuals, simulations, calibration, and plan selection.

**Required comparison dimensions:**

- action type and product/instance;
- support status;
- total/effective cost where supplied;
- stack change;
- requirement coverage;
- material exceptions and conditions;
- evidence freshness/quality;
- evaluation stability;
- company-aware result versus generic result; and
- reason/evidence details on demand.

Show every returned option, not an arbitrary first six. Keep columns aligned across options.
Do not collapse evidence, uncertainty, cost, stack risk, and coverage into an opaque “fit percentage.” Seller-authored positioning must be clearly labeled and must not affect ranking.

**Supported status vocabulary:**

- `SUPPORTED`
- `SUPPORTED_WITH_EXCEPTION`
- `NEEDS_CONDITION`
- `BLOCKED_BY_COMPANY_REQUIREMENT`
- `VENDOR_NOT_SUPPORTED`
- `UNAVAILABLE`
- `NEEDS_EVIDENCE`
- `EVIDENCE_CONFLICT`
- `AUTHORITY_REQUIRED`
- `RESEARCH_ONLY`

Use readable labels, but preserve exact semantics. In particular, a company block must not look like seller non-support.

**Option actions:**

- `KEEP_FOR_COMPARISON`
- `ELIMINATE`
- `ASK_VENDOR`
- `SAVE`
- `NEED_EVIDENCE`

Feedback does not change ranking by default. `ASK_VENDOR` is the only option action that may cross the buyer/seller boundary, and it is forbidden for a private request.

**Selection:**

- Render selection only when declared by the server.
- Never infer a primary option from array order.
- Submit `solution_plan_id`, `decision_version`, and `decision_hash` exactly as returned.
- Explain that selection creates an immutable selected decision version; it is not approval, payment, or execution.
- If rank stability is `UNSTABLE` or `UNDETERMINED`, follow the server action/error contract rather than manufacturing a bypass.

**No eligible option:** Render the dedicated decision outcome `NO_ELIGIBLE_SUPPORTED_ACTION`. Do not show a disabled purchase button or force a bad option.

### 9.6 Action — Decision Room stage — A with backend gaps

**Purpose:** Turn a selected action into an authorized, traceable execution plan.

**Primary APIs:** plan selection, action run, purchase intent, approval, checkout, purchase status, Stackfile.

Organize the page as a sequence, not a pile of status cards:

```text
Review exact selection -> Obtain authority -> Execute or assign -> Verify
```

**Required sections:**

- exact selected plan and decision hash/version;
- what will change and what will not;
- execution owner and current checkpoint;
- approval status and ordered required roles;
- payment status, if payment is required;
- fulfillment/deployment status;
- proposed Stackfile patch;
- blocking task and recovery action from the server; and
- activity/audit timestamps.

**Important:** `POST /action-runs` and `GET /action-runs/{id}` exist, but there is currently no general API for advancing or retrying arbitrary execution steps. The present fixture may remain `WAITING_FOR_HUMAN`. Do not implement no-op “Continue” controls. Render only a returned action descriptor or a separately contracted endpoint.

### 9.7 Result — Decision Room stage — A with backend gaps

**Purpose:** Show what actually happened, not what was merely selected or paid for.

**Primary APIs:** action run, purchase status, receipt, Stackfile, Decision View.

**Required result distinctions:**

- merchant order created;
- payment reconciled;
- entitlement or fulfillment verified;
- receipt available;
- Stackfile patch proposed/applied;
- deployment verified; and
- outcome measurement pending/recorded.

**Current limitation:** the Decision View currently does not make `RESULT` the active projected stage and returns empty result artifacts in the tested flow. The UI may design the complete state, but functional Result acceptance depends on backend projection/progression work.

Never label payment success as deployment or business outcome success.

### 9.8 Receipt — drawer or `/receipts/{purchaseId}` — A

**Purpose:** Display a verified receipt after payment reconciliation and fulfillment verification.

**Primary API:** `GET /v1/purchases/{purchaseId}/receipt`

Handle `RECEIPT_NOT_AVAILABLE` as a valid not-yet-ready state. Do not synthesize a receipt from purchase or checkout data.
Do not create a receipt for a no-charge path, and do not label a paid-but-unfulfilled purchase as declined.

### 9.9 Seller home — `/seller` — Mixed A/B

**Purpose:** Give a seller a short actionable view of products needing work.

There is no aggregate seller dashboard endpoint. A functional first build should either:

- make product search the seller landing page; or
- derive a small local view only from products explicitly returned by an agreed API call.

Do not invent aggregate review queues, opportunities, causal conversion analytics, or product counts.

### 9.10 Seller product search — `/seller/products/search` — A

**Purpose:** Find a product and enter or begin its evidence lifecycle.

**Primary API:** `GET /v1/seller/products/search?q=...`

**Requirements:**

- Send `q` to the API when it contains 2–200 characters.
- Support the API’s public-safe product result shape.
- Show claim/evidence status without exposing another seller’s private data.
- Provide an empty state and a safe no-access/not-found state.
- Do not load a full product list and pretend browser filtering is server search.

### 9.11 Seller Product Evidence — `/seller/product-evidence/{productId}` — A

**Purpose:** Provide one coherent console for claim, drafting, evidence, review, publication, versions, exports, and observational activity.

**Primary payload:** `GET /v1/seller/products/{productId}/view`

Recommended tabs or sections:

1. **Overview:** product, authority, pack health, validation, current review, published version, and next authorized action.
2. **Claims and rules:** structured claims, fit rules, and anti-fit rules.
3. **Evidence:** sources attached to claim fields, source class, and observation date.
4. **Review:** validation, submission hash, independent review, changes requested, and decision reason.
5. **Publication and exports:** current publication metadata and JSON/HTML/reusable-answer exports.
6. **Activity:** labeled observational metrics with measurement window.

**Lifecycle:**

```text
UNCLAIMED -> CLAIM_PENDING -> SELLER_DRAFT -> IN_REVIEW -> PUBLISH_READY -> PUBLISHED
```

Branches include:

- `CLAIM_DENIED`
- `VALIDATION_CONFLICT`
- `CHANGES_REQUESTED`
- `PUBLICATION_FAILED`
- `SUPERSEDED`

**Claim:** collect a 3–500 character authority proof reference and requested role. There is no seller-facing claim approval/denial endpoint, so `CLAIM_PENDING` is a waiting state. The authority proof is submitted to the server but must not be echoed back into ordinary browser views.

**Editing:** fetch the draft, submit `base_revision`, replace only contract-supported arrays, and reload after `SELLER_DRAFT_REVISION_CONFLICT`.

**Evidence:** the API accepts a source reference and metadata, not a binary file upload. Do not build a file uploader without a new backend contract.

**Review and publish:** bind actions to the exact `revision_hash`. Enforce editor/reviewer separation through server capability/actions and explain it clearly. Publication requires independent approval and step-up verification.

**Published versions:** are immutable. A new published version supersedes the prior one. Suspension is a separate high-authority action.

The product view may return current/previous version-link metadata, but there is no public endpoint for loading a version-detail page and the current version links target a route that is not implemented. Show only the publication metadata available in the primary payload. Do not render dead version-detail links; a navigable version history requires additional backend and route scope.

**Authority labels:** distinguish `SELLER_SEALED`, `PLATFORM_COMPILED`, and `EXTERNAL_UNSEALED`. Authority is not the same as truth or independent verification.

## 10. Buyer workflows that must be represented

### 10.1 Standard decision

```text
Create request
-> start discovery
-> follow workflow progress
-> inspect company fit and frozen rules
-> compare all supported actions
-> select an exact plan
-> start execution
-> verify result
```

### 10.2 Purchase requiring approval

```text
Select exact plan
-> create purchase intent
-> create approval request
-> complete required roles in order
-> create Prava hosted-checkout session
-> leave for hosted checkout
-> process authenticated return
-> poll workflow and purchase status
-> verify fulfillment
-> show verified receipt
```

Approval, payment, fulfillment, deployment, and outcome must remain visually and semantically distinct.

### 10.3 Selective seller engagement

The expected progression is:

```text
NOT_STARTED
-> SELLER_REVIEWING
-> SELLER_PASSED or OFFER_AVAILABLE
-> BUYER_CONSENT_PENDING
-> SELLER_CONSENT_PENDING
-> INTRODUCTION_READY
```

Alternative terminal states include `DECLINED` and `EXPIRED`.

Do not reveal contact details before valid mutual consent. Contact consent is not purchase approval. Decline or expiry must remove previously revealed contact details, and replaying stale consent must not restore them.

### 10.4 Counterfactual explanation

The demo’s important product proof is that a company-private fact can change the result. For example, the company-aware result may favor a supported replacement at a higher price, while a generic context favors the cheapest candidate. The UI should explain:

- what the generic result was;
- what the company-aware result is;
- which visible private facts changed it;
- which facts remain hidden; and
- why the result is stable or unstable.

Do not reveal hidden facts to unauthorized users or sellers.

## 11. State families

### 11.1 Decision stages

`NEED`, `COMPANY_FIT`, `OPTIONS`, `ACTION`, `RESULT`

### 11.2 Decision outcomes

- `SELECTED_SOLUTION_PLAN`
- `NO_ELIGIBLE_SUPPORTED_ACTION`

### 11.3 Rank stability

- `STABLE`
- `UNSTABLE`
- `UNDETERMINED`

### 11.4 Long-running operation

- `QUEUED`
- `RUNNING`
- `WAITING_FOR_HUMAN`
- `RETRYABLE_ERROR`
- `UNCERTAIN`
- `COMPLETED`
- `FAILED_FINAL`

### 11.5 Approval

- `NOT_REQUIRED`
- `NOT_REQUESTED`
- `PENDING`
- `APPROVED`
- `REJECTED`
- `EXPIRED`
- `SUPERSEDED`

### 11.6 Payment

- `NOT_REQUIRED`
- `NOT_STARTED`
- `SESSION_CREATED`
- `CARDHOLDER_PENDING`
- `CHECKOUT_PENDING`
- `MERCHANT_APPROVED`
- `REPORTING`
- `PRAVA_COMPLETED`
- `DECLINED`
- `EXPIRED`
- `UNCERTAIN`
- `FAILED`

### 11.7 Fulfillment

- `NOT_REQUIRED`
- `NOT_STARTED`
- `PENDING`
- `PARTIAL`
- `VERIFIED`
- `FAILED_RETRYABLE`
- `FAILED_FINAL`
- `REVOKED`

### 11.8 Stage status

- `NOT_STARTED`
- `READY`
- `CURRENT`
- `WAITING`
- `BLOCKED`
- `COMPLETED`
- `SUPERSEDED`

### 11.9 Execution-step status

- `NOT_REACHED`
- `AVAILABLE`
- `CURRENT`
- `BLOCKED`
- `COMPLETED`
- `SKIPPED`
- `FAILED_RETRYABLE`
- `FAILED_FINAL`

### 11.10 Composed purchase state

- `AWAITING_APPROVAL`
- `APPROVED_NOT_STARTED`
- `PAYMENT_IN_PROGRESS`
- `PAYMENT_NOT_COMPLETED`
- `PAYMENT_UNCERTAIN`
- `PAID_UNFULFILLED`
- `PURCHASE_FULFILLED`
- `REFUND_PENDING`
- `REFUNDED`

### 11.11 Deployment state

- `NOT_STARTED`
- `STAGED`
- `ACTIVE`

### 11.12 Outcome state

- `NOT_MEASURED`
- `MEASURING`
- `ACHIEVED`
- `NOT_ACHIEVED`

These are canonical values returned by `PurchaseStatusView`; translate them into readable labels but do not save a competing frontend state.

### 11.13 Version and selection state

- Decision version: `CURRENT`, `SUPERSEDED`.
- Plan selection: `SELECTED`, `SUPERSEDED`, `CANCELLED`.

## 12. API integration architecture

### 12.1 Base URL and proxy

Use same-origin browser requests to `/v1/...`. The API has no CORS middleware. The Next.js application currently proxies `/health` and `/v1/*` to the backend through `SIRA_API_BASE_URL`.

### 12.2 Authentication

Every endpoint except `/health` is protected.

Production requests use:

```http
Authorization: Bearer <credential>
```

The server identity adapter must resolve organization, actor, roles, party, human/service identity, and step-up status. Browser-supplied development identity headers are ignored in production.

The repository does not yet implement a production identity adapter, login/session API, or production web auth flow. This is a production blocker and must be resolved before a public launch.

### 12.3 Development identity

Development fixtures can use explicitly enabled `X-Organization-Id`, `X-Actor-Id`, `X-Actor-Roles`, `X-Step-Up-Verified`, `X-Identity-Kind`, and `X-Actor-Party` headers. These must never become a production identity mechanism or a user-editable browser preference.

### 12.4 Idempotency

Most mutations require `Idempotency-Key`, 8–128 characters.

- Generate one key per logical user action.
- Retain the key and exact body while a request is unresolved.
- Reuse both only for a retry of the same action.
- A changed body with the same key causes `IDEMPOTENCY_CONFLICT`.
- Do not generate a fresh key for every automatic retry.

### 12.5 Exact concurrency bindings

Preserve and resubmit:

- Decision: `decision_version` plus `decision_hash`.
- Seller editing: `base_revision`.
- Seller review/publish: `revision_hash`.
- Approval: `intent_hash`.

There are no ETags or `If-Match` headers. On a `409`, reload the canonical resource and clearly explain what changed before allowing another submission.

### 12.6 Asynchronous operations

A `202` often returns:

```json
{
  "workflow_id": "...",
  "status_url": "/v1/workflows/...",
  "events_url": "/v1/workflows/.../events"
}
```

The event stream is a finite snapshot and closes. It is not a permanent push connection. Reconnect or poll `status_url` until a terminal state, using sensible backoff and visible progress.

Native `EventSource` cannot attach a Bearer header. Use authenticated fetch streaming or polling.

### 12.7 Server action descriptors

Action descriptors may include `id`, `label`, `method`, `href`, confirmation requirement, and expiry. They are authoritative. The frontend may map known action IDs to suitable components, but must not change their authority, infer missing actions, or treat first-item order as priority.

### 12.8 Fixture and API modes

The current web application supports `NEXT_PUBLIC_WEB_DATA_MODE=fixture|api`; development defaults to fixture and production defaults to API.

- Clearly mark fixture mode in non-production builds.
- Never ship fixture identities or fixture success states as production behavior.
- Mutations are incomplete/disabled in fixture mode; functional acceptance must run against API mode.

## 13. Public endpoint reference

This is the current public surface. There is no `/v2` URL namespace even though part of the backend implementation is named `routes_v2.py`.

`Idem` means an `Idempotency-Key` is required.

### 13.1 Runtime and workflows

| Method | Path | Response | UI use |
|---|---|---|---|
| GET | `/health` | `HealthResponse` | Service status; public. |
| POST | `/v1/demo/reset` | object | Development/test fixtures only. |
| GET | `/v1/workflows/{workflowId}` | `WorkflowView` | Poll asynchronous work. |
| GET | `/v1/workflows/{workflowId}/events` | SSE | Fetch finite workflow-event snapshot. |

### 13.2 Decisions and company context

| Method | Path | Request / response | Authority and notes |
|---|---|---|---|
| GET | `/v1/decision-requests` | `DecisionIndexView` | `can_view_context`; no pagination/filter query. |
| POST | `/v1/decision-requests` | `DecisionRequestCreate` -> `DecisionRequestView` | `201`, Idem, `can_submit_request`. |
| GET | `/v1/decision-requests/{requestId}` | `DecisionRequestView` | Request header and progress. |
| POST | `/v1/decision-requests/{requestId}/discover` | `WorkflowAccepted` | `202`, Idem. |
| GET | `/v1/decision-requests/{requestId}/decision-view` | `DecisionView` | Primary Decision Room payload. |
| GET | `/v1/decision-requests/{requestId}/decision-rules` | `DecisionRulesView` | Frozen rules and content hash. |
| POST | `/v1/decision-requests/{requestId}/calibration-runs` | `CalibrationRunCreate` -> `CalibrationRunView` | `201`, Idem. |
| POST | `/v1/decision-requests/{requestId}/solution-options/{planId}/actions` | `OptionFeedbackCreate` -> `OptionFeedbackView` | `201`, Idem, authorized recommendation selector. |
| POST | `/v1/decision-rules/{rulesId}/proposals/{proposalId}/accept` | `ProposalDecisionCreate` -> `ProposalDecisionView` | Idem, human, authorized role and step-up. |
| POST | `/v1/decision-rules/{rulesId}/proposals/{proposalId}/reject` | Same | Same authority as accept. |
| GET | `/v1/decisions/{decisionId}` | `DecisionLedgerV2` | Immutable evidence and evaluation ledger. |
| GET | `/v1/decisions/{decisionId}/counterfactuals` | `CounterfactualView` | Generic versus company-aware explanation. |
| POST | `/v1/decisions/{decisionId}/simulations` | `DecisionSimulationCreate` -> `DecisionSimulationView` | `201`, Idem; always non-authoritative/no ranking effect. |
| POST | `/v1/evaluation-runs/{evaluationRunId}/replay` | `EvaluationReplayView` | Diagnostic/audit replay. |
| POST | `/v1/decisions/{decisionId}/plan-selections` | `PlanSelectionCreate` -> `PlanSelectionView` | `201`, Idem, human and step-up. |
| POST | `/v1/decisions/{decisionId}/action-runs` | `ActionRunCreate` -> `ActionRunView` | `202`, Idem, human. |
| GET | `/v1/action-runs/{actionRunId}` | `ActionRunView` | Durable execution state. |
| GET | `/v1/organizations/{organizationId}/stackfile` | `StackfileView` | Path organization must match authenticated tenant. |

### 13.3 Selective seller engagement

| Method | Path | Request / response | Notes |
|---|---|---|---|
| GET | `/v1/requirement-briefs/{briefId}` | `RequirementBriefView` | Seller-safe and role-filtered; seller must be active participant. |
| POST | `/v1/engagements/{engagementId}/consent` | `ConsentCreate` -> `EngagementView` | Idem; verified buyer or seller party. |

### 13.4 Purchase, approval, checkout, and receipt

| Method | Path | Request / response | Authority and notes |
|---|---|---|---|
| POST | `/v1/decisions/{decisionId}/purchase-intents` | `PurchaseIntentCreate` -> `PurchaseIntentView` | `201`, Idem; freezes exact quote, policy, plan, merchant, and hashes. |
| POST | `/v1/purchase-intents/{intentId}/approval-requests` | `{}` -> `ApprovalRequestView` | `201`, Idem, procurement-gate authority. |
| POST | `/v1/approval-requests/{approvalId}/approve` | `ApprovalCreate` -> `ApprovalRequestView` | Idem, human, verified role, ordered stage, step-up. |
| POST | `/v1/approval-requests/{approvalId}/reject` | `ApprovalRejectCreate` -> `ApprovalRequestView` | Same, plus reason. |
| POST | `/v1/purchase-intents/{intentId}/prava-sessions` | `PravaSessionCreate` -> `PravaSessionView` | `201`, Idem, human, execution authority, step-up. |
| GET | `/v1/prava/browser-return?state=...&return_url=...` | `WorkflowAccepted` | `202`; consumes one-time actor-bound checkout return. |
| GET | `/v1/purchase-intents/{intentId}/status` | `PurchaseStatusView` | Canonical composed purchase status. |
| GET | `/v1/purchases/{purchaseId}/receipt` | `ReceiptView` | Only after reconciliation and verified fulfillment. |

### 13.5 Seller Product Evidence

| Method | Path | Request / response | Authority and notes |
|---|---|---|---|
| GET | `/v1/seller/products/search?q=...` | `SellerProductSearchView` | Seller-scoped; `q` is optional, 2–200 when supplied. |
| POST | `/v1/seller/products/{productId}/claim` | `SellerClaimCreate` -> `SellerClaimView` | `201`, Idem, seller human. |
| GET | `/v1/seller/products/{productId}/view` | `SellerEvidenceView` | Primary seller page payload. |
| GET | `/v1/seller/pack-drafts/{draftId}` | `SellerPackDraftView` | Scoped current draft. |
| PATCH | `/v1/seller/pack-drafts/{draftId}` | `SellerPackDraftPatch` -> `SellerPackDraftView` | Idem, human, editor/platform, requires `base_revision`. |
| POST | `/v1/seller/pack-drafts/{draftId}/evidence` | `SellerEvidenceAttachCreate` -> `SellerEvidenceAttachmentView` | `201`, Idem, human. |
| POST | `/v1/seller/pack-drafts/{draftId}/submit-review` | `SellerSubmitReviewCreate` -> draft | Idem, human, exact `revision_hash`. |
| POST | `/v1/seller/pack-drafts/{draftId}/review-decisions` | `SellerReviewDecisionCreate` -> decision | `201`, Idem, independent reviewer/platform. |
| POST | `/v1/seller/pack-drafts/{draftId}/publish` | `SellerPublishCreate` -> `SellerPackVersionView` | `201`, Idem, reviewer/platform, step-up. |
| POST | `/v1/seller/pack-versions/{versionId}/suspend` | `SellerSuspendCreate` -> `SellerPackVersionView` | Idem, reviewer/platform, step-up. |
| GET | `/v1/seller/pack-versions/{versionId}/exports` | `SellerPackExportsView` | JSON, HTML, and reusable-answer descriptors. |
| GET | `/v1/seller/products/{productId}/activity-metrics` | `SellerActivityMetrics` | Observational, non-causal metrics. |

### 13.6 Hidden legacy routes

Do not build against routes with `include_in_schema=False`, including:

- `/v1/purchase-requests...`;
- `/v1/purchase-briefs/.../proposals...`;
- legacy candidate-action endpoints;
- `POST /v1/prava/browser-return`; and
- the hidden duplicate legacy Decision endpoint.

Use only the frozen OpenAPI operations.

## 14. Important request shapes

| Action | Required binding or fields |
|---|---|
| Create Decision Request | `intent`; optional `desired_outcome`, `deadline`, `incumbent_instance_id`, `visibility`. |
| Option feedback | `action`, `reason` 3–1000 chars, optional proposed criterion change. |
| Select plan | `solution_plan_id`, `decision_version`, `decision_hash` matching `sha256:<64 hex>`. |
| Start action run | Same exact plan/version/hash binding. |
| Create Prava session | `return_url`; must meet configured HTTPS web-origin policy outside local development. |
| Approve | `intent_hash`, verified `actor_role`. |
| Reject | `intent_hash`, verified `actor_role`, `reason`. |
| Consent | `consent`, scope currently `CONTACT_EXCHANGE`. |
| Seller claim | `authority_proof_reference` 3–500 chars, optional requested role. |
| Seller draft patch | `base_revision` plus contract-supported replacement arrays. |
| Attach seller evidence | `source_reference`, `source_class`, `claim_fields[]`, optional `observed_at`. |
| Submit/review/publish seller draft | Exact `revision_hash`; review also includes decision and reason. |
| Suspend version | `reason`, `effective_at`. |

Accepted seller evidence source classes are `VENDOR_DOCUMENTATION`, `SECURITY_ATTESTATION`, `CONTRACT`, `PUBLIC_WEB`, and `SELLER_ASSERTION`.

## 15. Error, loading, and recovery design

### 15.1 Error envelope

Handled errors use:

```json
{
  "error": {
    "code": "STABLE_MACHINE_CODE",
    "message": "Safe user-facing explanation",
    "request_id": "rq_...",
    "retryable": false,
    "next_action": "optional_machine_hint",
    "details": {}
  }
}
```

Every response includes `X-Request-Id`. Show it under expandable support details, not as the main error copy.

### 15.2 HTTP treatment

| Status | Meaning | UI behavior |
|---:|---|---|
| 400 | Invalid semantics or state | Explain the corrective action; preserve safe input. |
| 401 | Authentication missing/invalid | Send through the approved sign-in/session recovery flow when it exists. |
| 403 | Permission, party, tenant, human, or step-up denial | Do not retry automatically or reveal protected data. Offer step-up only when contractually supported. |
| 404 | Resource unavailable in the actor’s scope | Use a safe unavailable page; do not distinguish “exists for someone else.” |
| 409 | Version/hash/state/idempotency conflict | Reload canonical state and show what must be reviewed again. |
| 422 | Strict request validation | Map field errors; extra fields are forbidden. |
| 502 | Provider rejection/final provider failure | Show provider-safe explanation and support path. |
| 503 | Dependency, identity, setup, database, or retryable provider failure | Respect `retryable`; preserve exact idempotency key/body. |

### 15.3 Required non-happy states

Every functional page must include designs and implementation for:

- initial loading;
- no data/first use;
- partial data;
- background refresh;
- slow workflow;
- offline/disconnected;
- retryable failure;
- final failure;
- uncertain external outcome;
- no authority;
- expired step-up/session/action;
- stale exact version;
- resource superseded;
- no eligible supported action; and
- safe not found.

### 15.4 High-value conflicts

Buyer:

- `DECISION_SUPERSEDED`
- `DECISION_VERSION_HASH_MISMATCH`
- `SOLUTION_OPTION_NOT_SELECTABLE`
- `RANK_NOT_STABLE`
- `PLAN_SELECTION_REQUIRED`
- `QUOTE_EXPIRED`
- `APPROVAL_EXPIRED`
- `APPROVAL_STAGE_OUT_OF_ORDER`
- `SEPARATION_OF_DUTIES`
- `APPROVAL_REQUIRED`
- `SESSION_CREATE_RECONCILIATION_REQUIRED`
- `PROVIDER_SETUP_BLOCKED`
- `CALLBACK_STATE_REPLAYED`
- `RECEIPT_NOT_AVAILABLE`

Seller:

- `SELLER_DRAFT_REVISION_CONFLICT`
- `SELLER_REVISION_HASH_MISMATCH`
- `SELLER_DRAFT_FROZEN`
- `SELLER_DRAFT_VALIDATION_FAILED`
- `SELLER_REVIEW_NOT_PENDING`
- `SELLER_EDITOR_REVIEWER_SEPARATION_REQUIRED`
- `SELLER_DRAFT_NOT_PUBLISH_READY`
- `SELLER_REVIEW_APPROVAL_REQUIRED`

## 16. Design-system and interaction requirements

The contractor should propose the final design system. At minimum it must include:

- semantic color tokens for neutral, information, supported, warning, blocked, error, and uncertain states;
- typography suitable for dense evidence without feeling like an admin console;
- spacing and layout tokens;
- buttons, links, form controls, comboboxes, date inputs, dialogs, drawers, tabs, tables, status labels, progress, alerts, and empty states;
- a comparison pattern that works with variable content;
- evidence/provenance disclosure patterns;
- immutable version/hash display with a readable short form and copy detail;
- approval timeline and long-running-operation patterns;
- responsive navigation;
- focus, hover, active, disabled, loading, expired, and destructive states; and
- light/dark behavior only if dark mode is explicitly included in the contract.

### 16.1 Content style

- Lead with the decision or task, then explain evidence.
- Translate enum values into concise labels without changing meaning.
- Avoid anthropomorphizing the system or implying human judgment where it is deterministic.
- Never say “approved” for “selected,” “paid” for “merchant approved,” or “done” for “payment completed but fulfillment unverified.”
- Put technical identifiers in expandable details unless the identifier is needed to compare immutable versions.

### 16.2 Accessibility

Functional acceptance requires WCAG 2.2 AA:

- complete keyboard operation;
- visible focus;
- semantic landmarks and headings;
- screen-reader names and status announcements;
- no color-only meaning;
- sufficient contrast;
- error association and recovery;
- reduced-motion support;
- usable zoom/reflow; and
- accessible comparison on narrow screens.

## 17. Responsive requirements

Support current evergreen desktop and mobile browsers. Validate at minimum:

- 360px phone;
- 768px tablet;
- 1280px laptop; and
- 1440px desktop.

The desktop interface should not assume three persistent panes. Use the space required by the current task. Evidence detail can move to a drawer or subordinate region, and navigation may collapse, but the primary action and current status must remain visible and understandable.

## 18. Security and privacy requirements

- Never store provider secrets, API keys, payment credentials, or raw bearer tokens in frontend source or logs.
- Never pass Prava’s one-time payment credential through ordinary UI state.
- Do not expose development identity headers in production.
- Never infer or display private fact names/values from `hidden_fact_count`.
- Treat 404s as scope-safe unavailable responses.
- Do not send buyer-private context to seller APIs.
- Do not reveal contacts before mutual consent.
- Do not allow the browser to authorize itself by changing a role/workspace switch.
- Confirm sensitive/destructive actions when the server descriptor requires confirmation.
- Expired action descriptors must be refreshed, not executed.
- Render backend messages as text; never inject server HTML unless a narrowly reviewed export renderer is used.

## 19. Known backend dependencies and gaps

The outsourced team must not hide these gaps with local-only behavior.

1. **Production identity is unresolved.** No production identity adapter or login/session API is included.
2. **Authenticated checkout return needs architecture.** An external browser redirect cannot add a Bearer header to the current protected callback. A same-origin authenticated callback/BFF or revised contract is required.
3. **Generated client query typing is incomplete.** The generator currently omits query parameters for seller `q` and Prava `state`/`return_url`. Fix generation or add a reviewed typed URL helper.
4. **Need editing is absent.** There is no update endpoint for an existing Decision Request.
5. **Inbox/home/settings APIs are absent.** Current data on those pages is hard-coded.
6. **Decision list scale controls are absent.** No pagination, search, sort, or server filters.
7. **Approval detail/inbox APIs are absent.** There is no standalone GET approval request or approval inbox.
8. **Purchase-intent detail is absent.** Status exists, but there is no general GET full purchase intent by ID.
9. **Result projection is incomplete.** The current Decision Room does not make Result the current stage and result artifacts are empty.
10. **Action progression is incomplete.** Start/get exist, but no general progression/retry contract exists beyond returned descriptors.
11. **Seller claim review is absent.** Sellers can submit a claim but cannot approve/deny it.
12. **Seller binary upload is absent.** Evidence uses source references only.
13. **Seller suspension projection needs completion.** Validate current-version behavior before accepting the final screen.
14. **No complete browser end-to-end path exists.** Commerce is tested in backend integration tests, not a full Playwright UI journey.
15. **Seller version detail is absent.** Product projections can return version-link metadata, but no public endpoint loads an individual seller pack version for the future version-detail route.

These items should become separately estimated backend tasks or explicit exclusions.

## 20. Contractor deliverables

### 20.1 Product and UX

- validated information architecture;
- user flows for the standard decision, no-eligible outcome, approval/checkout, selective seller engagement, and seller publication;
- low-fidelity wireframes for all build-now routes and important non-happy states;
- clear recommendation on which design-only routes to include or remove;
- content/copy pass for status and recovery language; and
- an open-questions/dependency log.

### 20.2 Visual design

- at least two genuinely different visual directions for early review;
- approved high-fidelity desktop and mobile screens;
- reusable design system and tokens;
- components and variants for all state families;
- clickable prototype covering the core buyer and seller flows; and
- design source files with organized components, variables, and handoff annotations.

### 20.3 Frontend implementation

- production-quality Next.js/React/TypeScript code in `apps/web`;
- use of the generated API client and types;
- a centralized query/mutation, idempotency, async workflow, and error strategy;
- accessible responsive implementation;
- no fixture data in API-mode screens;
- no no-op controls or dead links;
- route-level loading, errors, safe not-found behavior, and recovery;
- component/unit tests for important interactions;
- accessibility tests;
- Playwright journeys for supported end-to-end paths; and
- updated frontend setup and architecture documentation.

### 20.4 Handoff

- route-to-endpoint traceability matrix;
- list of backend blockers and any contract changes requested;
- test report and browser/device matrix;
- known limitations;
- instructions for adding a page, action descriptor, and status mapping; and
- no unreviewed changes to the frozen OpenAPI contract.

## 21. Recommended delivery milestones

1. **Alignment:** confirm scope labels, backend exclusions, roles, and acceptance journeys.
2. **UX:** information architecture, flows, wireframes, and complete state inventory.
3. **Visual direction:** compare alternatives and approve one system.
4. **Foundation:** shell, tokens, accessibility baseline, typed API layer, errors, idempotency, and async workflow handling.
5. **Buyer implementation:** decision list, creation, five-stage room, selection, action, purchase, and receipt states.
6. **Seller implementation:** search and complete supported evidence lifecycle.
7. **Hardening:** responsive work, edge states, accessibility, automated tests, and performance.
8. **Handoff:** documentation, gap list, demo, and acceptance sign-off.

Do not postpone state design until after the happy-path screens. State completeness is part of UX, not QA cleanup.

## 22. Acceptance criteria

The delivery is accepted only when:

- the result is an original redesign and does not visually reproduce the current prototype;
- every build-now route has a clear purpose and primary action;
- all functional data in API mode comes from the public typed API;
- no hidden legacy route is used;
- every mutation uses correct idempotency behavior;
- exact hashes/revisions are preserved and stale conflicts recover safely;
- available actions/capabilities drive authorization-sensitive controls;
- all returned solution options are available for comparison;
- company blocks and seller non-support are distinct;
- selection, approval, payment, fulfillment, deployment, and result are distinct;
- buyer/seller privacy boundaries and mutual consent are respected;
- long-running, uncertain, retryable, and final states are designed and implemented;
- there are no fake chat interactions, no-op buttons, broken version links, or hard-coded user/task data in API mode;
- core pages meet WCAG 2.2 AA and the responsive matrix;
- unit/component/accessibility tests pass;
- supported buyer and seller Playwright journeys pass; and
- all documented backend gaps remain explicit rather than masked with local state.

### 22.1 Required acceptance journeys

At minimum, demonstrate:

1. Create a request, run discovery, compare all options, select an exact supported non-purchase action, and reach the available execution state.
2. See a company-aware recommendation differ from a generic result and inspect a safe counterfactual explanation.
3. Reach `NO_ELIGIBLE_SUPPORTED_ACTION` without a misleading purchase action.
4. Ask a seller, complete two-party contact consent, and reveal contacts only when allowed.
5. After the authenticated checkout-return/BFF dependency in section 19 is resolved, select a purchase action, create ordered approval, launch checkout, recover from the browser return, poll status, and display a verified receipt in a configured provider environment.
6. Submit a seller product claim and verify the canonical `CLAIM_PENDING` state. In a separate fixture that begins at a pre-approved `SELLER_DRAFT`, edit by base revision, attach referenced evidence, submit the exact revision, complete independent review, publish, export, and suspend where authorized.
7. Recover from a stale Decision hash and a stale seller draft revision without losing safe user input.

## 23. Local development and verification

From the repository root on Windows, install the frozen dependencies and create the local environment first:

```powershell
corepack prepare pnpm@11.9.0 --activate
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

Start PostgreSQL and apply migrations:

```powershell
docker compose up -d postgres
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\migrate.ps1
```

Then start the API in one PowerShell terminal:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-api.ps1
```

Start the web application in a second PowerShell terminal:

```powershell
corepack pnpm dev:web
```

The API is at `http://127.0.0.1:8000`, OpenAPI documentation is at `http://127.0.0.1:8000/docs`, and the web app is at `http://localhost:3000`.

Run the repository checks before handoff:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check.ps1
```

For frontend work specifically:

```powershell
corepack pnpm check:web
```

When the public API changes, regenerate and check the frozen contract/client rather than editing generated files manually.

## 24. Repository references

- Product requirements: [`docs/PRD.md`](PRD.md)
- Build contract: [`docs/BUILD_SPEC.md`](BUILD_SPEC.md)
- Semantic/design background: [`DESIGN.md`](../DESIGN.md)
- Frozen OpenAPI: [`contracts/openapi/openapi.json`](../contracts/openapi/openapi.json)
- Generated client: [`packages/api-client/src/client.ts`](../packages/api-client/src/client.ts)
- Generated types: [`packages/api-client/src/types.ts`](../packages/api-client/src/types.ts)
- Current web app: [`apps/web`](../apps/web)
- Decision Room routes: [`services/api/sira_api/routes_v2.py`](../services/api/sira_api/routes_v2.py)
- Commerce/workflow routes: [`services/api/sira_api/routes.py`](../services/api/sira_api/routes.py)
- Seller routes: [`services/api/sira_api/seller_routes.py`](../services/api/sira_api/seller_routes.py)
- Decision API tests: [`tests/api/test_decision_room_api.py`](../tests/api/test_decision_room_api.py)
- Seller API tests: [`tests/api/test_seller_evidence_api.py`](../tests/api/test_seller_evidence_api.py)
- State-machine tests: [`tests/unit/test_domain_state_machines.py`](../tests/unit/test_domain_state_machines.py)
- Checkout integration: [`tests/integration/test_worker_checkout.py`](../tests/integration/test_worker_checkout.py)
- Browser-return integration: [`tests/integration/test_browser_return.py`](../tests/integration/test_browser_return.py)

---

This document defines the UI redesign engagement. Any feature marked B or C, any new persistence behavior, and any change to the frozen API contract requires explicit product and backend approval before implementation.
