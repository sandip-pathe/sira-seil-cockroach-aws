# SIRA + SEIL Product Design

- **Status:** Implementation baseline
- **Version:** 1.0
- **Mode:** Light only. Do not add a dark-mode theme or toggle.
- **Scope:** Shared public site, SIRA buyer workspace, SEIL seller workspace, shared exchange, settings, connectors, and internal operations.

This document controls target product surfaces, visual design, and interaction design. `docs/PRD.md` controls privacy, security, and authority; `docs/BUILD_SPEC.md` controls first-build contracts and required states. Future surfaces stay hidden until their role-filtered contracts exist. Security and authority rules always win without changing the paired SIRA/SEIL entry model defined here.

## 1. Product model

SIRA and SEIL are peer products on one platform. They share a design system and account shell, but each is dominant only inside its own workspace.

| | SIRA | SEIL |
|---|---|---|
| Represents | The buyer and its company | The product and its seller |
| Private working record | Buyer Passport and Company stack | Private Product Passport |
| Governed record | Purchase Brief and Decision rules | Reviewed Product Evidence and SEIL Pack |
| Cross-boundary output | Sanitized Requirement Brief | Positioning, structured plan, and offer |
| Primary outcome | Best supported company action | Reusable, current product truth and qualified offers |

The **Private Product Passport** is the seller's working record of sources, draft claims, roadmap/capacity, private commercial rules, positioning, fulfillment, and unpublished constraints. It is never buyer-visible. Only allowlisted, reviewed fields can become a published SEIL Pack.

The exchange is typed and consented, but contact consent and purchase authority are separate:

```text
SIRA Requirement Brief -> seller pass / missing-field request / offer
                       -> optional scoped mutual contact consent -> introduction

Buyer selects plan -> policy/budget approval -> cardholder authorization if charged
                   -> execution or assignment -> verification
```

Mutual contact consent reveals only the displayed contact scope; it never approves a plan, amount, payment, or execution. Never show SIRA and SEIL chatting with each other. Never mix buyer-private and seller-private records in one browser payload, cache, notification, or analytics event.

## 2. Experience principles

1. **One platform, two clear doors.** The landing page and signed-in home give SIRA and SEIL equal legitimacy.
2. **Chat gathers; records govern.** Conversation can capture and propose. Structured, versioned records validate, rank, publish, approve, execute, and verify.
3. **Ask only material questions.** Gather the minimum context needed to change eligibility, ranking, disclosure, publication, or execution. Do not harvest context for its own sake.
4. **Show the boundary.** Authorized actors who manage disclosure see Private, Shared in brief, Published, or Restricted. Other actors receive no restricted field or privacy mark at all.
5. **Truth before persuasion.** Evidence, uncertainty, fit, and anti-fit appear before seller positioning. Positioning is always labelled and never styled like rank evidence.
6. **Structured work becomes primary.** Chat is prominent during intake; the structured canvas becomes primary once a Brief, Passport, comparison, or execution exists.
7. **One safe primary action.** A filled primary appears only for the current server-authorized workflow action. Never infer priority from an action name or array order.
8. **Preserve known state.** Loading, failure, expiry, and reconnect never blank the last verified state or imply success.
9. **No opaque score.** Show eligibility, preference fit, Company-stack risk, cost, evidence, coverage, and stability separately.
10. **Inspired, not copied.** Use the calm three-pane workflow pattern, not Jack & Jill's characters, exact layout, colors, copy, emojis, or recruitment vocabulary.

## 3. Visual system

### 3.1 Color

Declare `color-scheme: light`. Ignore the operating-system dark preference. Exports, receipts, and print views also use the light palette.

| Token | Value | Use |
|---|---:|---|
| Canvas | `#F3F6F5` | Page and application background |
| Surface | `#FFFFFF` | Primary panels and forms |
| Surface subdued | `#E9EFEC` | Selected rows, quiet sections, skeletons |
| Ink | `#13201C` | Titles and primary text |
| Text | `#2B3833` | Body text |
| Muted | `#52615B` | Metadata and secondary copy |
| Border | `#CBD6D1` | Nonessential dividers and panels |
| Border strong | `#97A7A0` | Active divisions and tables |
| Control border | `#64736C` | Inputs and interactive control boundaries |
| SIRA | `#006B5F` | SIRA navigation, focus context, primary actions |
| SIRA soft | `#E4F2EF` | SIRA selection and quiet emphasis |
| SEIL | `#8A4B16` | SEIL navigation, focus context, primary actions |
| SEIL soft | `#FBF0E8` | SEIL selection and quiet emphasis |
| Focus | `#1D4ED8` | Keyboard focus only |
| Success | `#157347` / `#E7F4EC` | Verified completion |
| Warning | `#8A5A00` / `#FFF4D6` | Expiry, uncertainty, stale state |
| Danger | `#B42318` / `#FDECEA` | Destructive or failed state |
| Info | `#2E5AAC` / `#EAF0FF` | Neutral system information |

SIRA and SEIL accents identify workspace ownership. They never encode evidence quality, recommendation strength, payment status, or verification. Do not use gradients, glass effects, black hero blocks, decorative colored icon tiles, or confetti.

### 3.2 Typography and density

- **UI and headings:** self-hosted Geist Sans, with `Segoe UI, sans-serif` fallback.
- **Versions, hashes, timestamps, evidence metadata:** Geist Mono, with `Consolas, monospace` fallback.
- **Individual product wordmarks:** Montserrat Bold (`700`) in black. Do not synthesize bold from the regular face.
- **Shared landing display:** Instrument Serif may be used for one short hero line only. Never use it in application controls, dense records, or product wordmarks.
- **Scale:** hero 56/60, page title 32/38, section 22/28, body 15/22, comparison 14/20, metadata 12/16.
- **Spacing:** 4-pixel base; use 4, 8, 12, 16, 24, 32, and 48 pixels.
- **Controls:** 36 pixels compact, 44 pixels default; all touch targets are at least 44 by 44 pixels.
- **Shape:** 6-pixel controls, 10-pixel standard panels, 12-pixel dialogs; full pills only for short statuses.
- **Elevation:** borders provide hierarchy. Use one subtle shadow only for dialogs, drawers, menus, and sticky mobile controls.
- **Motion:** 120 ms feedback and 180 ms sheets using opacity/transform. Reduced motion removes nonessential transitions.
- **Icons:** simple 16/20-pixel line icons with text. No mascots, faces, product-character avatars, or decorative emojis.

### 3.3 Brand treatment

- Shared/public surfaces use the supplied black stacked SIRA/SEIL lockup. Use **Seilnsara** only for legal, billing, and corporate attribution.
- The browser favicon uses the supplied standalone black **S** mark.
- The workspace wordmark is only **SIRA** or **SEIL**, set in black Montserrat Bold (`700`). Do not place a boxed letter, glyph tile, or decorative product icon before it.
- Use identical typography and geometry for the two individual wordmarks. Accent color and nouns change elsewhere in the interface; quality and prominence do not.
- Buyer screens call a SEIL Pack **Product Evidence** unless provenance detail is open.
- Seller screens may use **Private Product Passport**, **Product Evidence**, and **SEIL Pack** because those distinctions control publication.

## 4. Shared information architecture

### 4.1 Entry and workspace switching

Logged-out users see one shared landing page with equal entry paths:

- **Decide with SIRA** - make, approve, execute, and verify a software decision.
- **Publish with SEIL** - compile private product knowledge into trusted Product Evidence and qualified offers.

After sign-in, `/home` shows only workspaces and organizations the server authorizes. A user with one workspace enters it directly. A user with both chooses SIRA or SEIL and can switch from the rail. Switching workspace or organization:

- warns about genuinely unsaved work;
- changes the visible wordmark, accent, navigation, and vocabulary;
- clears the prior workspace query cache and browser-derived state;
- never grants a role or tenant based on the selected UI value.

### 4.2 Application shell

Object workspaces use a three-pane grammar inspired by the reference screenshots. The structured canvas remains dominant; conversation is never required merely to inspect or complete structured work.

| Pane | Desktop behavior | Content |
|---|---|---|
| Object rail | 216 px, persistent on desktop | Workspace switch, navigation, recent objects, onboarding checklist, account/org |
| Conversation | 400-440 px, collapsible | Intake, Q&A, source uploads, proposed captures, progress, explanations |
| Structured canvas | Flexible, minimum 640 px when three panes show | Tabs, validated records, comparisons, workflow, evidence, actions |

The structured canvas owns the page URL and canonical state. The conversation stays attached to the current Decision or Product, not to a generic global thread. Details open in a 420-pixel drawer over the structured canvas. The target shell supports conversation in both products, but a page without a message/capture contract omits Chat rather than simulating an assistant.

Home, index, and settings pages may use a two-pane rail plus canvas layout. Do not force an empty chat column where no object conversation exists.

### 4.3 Responsive behavior

- **Wide desktop, `>=1440px`:** rail, optional conversation, and structured canvas may show together; the canvas receives the most space.
- **Desktop, `1024-1439px`:** persistent 216-pixel rail and dominant canvas. Conversation and details open as mutually exclusive 420-pixel overlay drawers.
- **Tablet, `640-1023px`:** rail collapses; one canvas fills the viewport; rail, conversation, and details use full-height sheets.
- **Mobile, `<=639px`:** one primary pane. Rail, conversation, and details are full-height sheets. Object pages provide sticky **Chat** and **Details** controls where available; the composer/action bar stays reachable above the keyboard.
- **Narrow mobile, 320 px:** no page-level horizontal scroll. Comparison becomes a vertical view with a sticky option switcher.
- Browser Back closes the topmost drawer/sheet before navigating stage or page history.

### 4.4 Visibility and cross-side exchange

- **Private:** SIRA evaluates without seller outreach. The Requirement Brief may be previewed but is not transmitted.
- **Selective:** the buyer chooses recipient SEIL workspaces and confirms the exact sanitized Brief before sending.
- **Open RFP:** qualified sellers may discover the sanitized Brief. This remains hidden until marketplace contracts and moderation exist.

Only **Ask vendor** crosses the trust boundary. Keep, Eliminate, Save, and Need evidence remain buyer-private. Seller responses are attributable anti-fit, an allowed missing-field request, or a structured offer. Buyer and seller identity/contact remain absent until both sides consent to the displayed scope.

The engagement drawer binds the exact Requirement Brief version, recipient, scope, and expiry. It renders these server states and only their returned safe actions:

| State | Treatment |
|---|---|
| `NOT_STARTED` | Preview the sanitized Brief; send only after buyer confirmation. |
| `SELLER_REVIEWING` | Show recipient, sent version, deadline, and withdrawal only when authorized. |
| `SELLER_PASSED` | Say **Vendor says not supported**; show attributable rule/remediation when disclosure permits; reveal no contacts. |
| `OFFER_AVAILABLE` | Show structured plan/terms, evidence, labelled seller positioning, quote expiry, and compare/continue actions. |
| `BUYER_CONSENT_PENDING` | Buyer accepts or declines the exact contact identity, fields, purpose, and expiry. |
| `SELLER_CONSENT_PENDING` | Preserve the buyer decision and wait/withdraw safely; reveal no seller contact. |
| `INTRODUCTION_READY` | Reveal only the consented contacts and scope; purchase authority remains separate. |
| `DECLINED` / `EXPIRED` | Reveal nothing new; continue privately, choose another option, or renew the request when allowed. |

## 5. Conversation and structured capture

### 5.1 Composer

The composer supports text, file upload, pasted URL, and optional dictation. It always displays the current privacy boundary, such as **Private to your company** or **Private to your seller workspace**.

Question cards contain:

- the question;
- why it is being asked;
- what may change when answered;
- Answer, Skip, and Mark unknown actions where allowed.

Chat may extract draft fields, locate missing facts, summarize cited sources, explain deterministic results, and propose edits. It cannot make a fact authoritative, change policy, publish, contact another party, select a plan, approve, pay, or mark completion.

Conversation appears only where the API supplies message, source, typed-capture, provenance, and confirmation contracts. Until then, the same work uses structured forms; the first-build seller route does not show a fake chat surface.

### 5.2 Capture flow

```text
Message or source
  -> proposed typed capture
  -> live Brief or Passport preview
  -> validation, provenance, privacy and conflict checks
  -> confirmation by an authorized human or verified connector under that field's policy
  -> new versioned record
```

Proposed captures look visibly provisional. Each shows source, confidence/unknown state, destination record, privacy state, and Accept/Edit/Reject when human confirmation is allowed. The field contract decides which roles and verified source classes may confirm it. Chat progress may say **3 sources read, 5 facts proposed** and expose activity detail; only the server workflow may report a step as completed or failed.

### 5.3 Conversation states

Use explicit states: Ready, Reading sources, Needs answer, Proposal ready, Waiting for owner, Completed step, and Failed safely. Stop auto-scrolling after the user scrolls away. Only the newest status line uses a polite live region; the whole thread is never live.

## 6. Page inventory

**First build** is locked by `BUILD_SPEC.md`. **Foundation** is required for the full paired product but remains behind a feature flag until its session/authorization projection exists. **Later** is hidden until its own contract exists. **Internal** is restricted to platform operators.

### 6.1 Public, authentication, and shared pages

| Page | Route | Phase | Required content |
|---|---|---|---|
| Shared landing | `/` | Foundation | Paired SIRA/SEIL hero, two entry CTAs, two-sided flow, trust boundary, example outcomes, connectors, security, pricing summary, footer |
| Sign in | `/sign-in` | Foundation | Work email/SSO, invitation handling, safe error and recovery |
| Invitation | `/join/{token}` | Foundation | Organization, offered role, expiry, accept/decline; no private preview before acceptance |
| Auth return | `/auth/return` | Foundation | Short progress state, replay-safe error, return destination |
| Workspace home | `/home` | Foundation | Authorized SIRA/SEIL cards, organizations, recent work, assigned tasks, activation checklist |
| Inbox | `/inbox` | Foundation | Workspace-filtered assignments, approvals, evidence requests, review/publication, execution, expiry, and outcome tasks |
| Public Product Evidence | `/evidence/{product_id}/versions/{version}` | Later | Immutable published fields, publisher authority, claim verification/freshness, superseded/suspended state, no private Passport |
| Security and trust | `/security` | Later | Privacy boundaries, evidence authority, approval/payment separation, responsible disclosure |
| Pricing | `/pricing` | Later | Buyer and seller packages; explicit statement that payment never buys rank |
| Legal | `/privacy`, `/terms` | Foundation | Approved legal content and effective version |
| Access denied/not found | shared | Foundation | Safe explanation, request-access or return action; no existence or tenant leak |

Landing sections use generous whitespace and strong type. Application screenshots must show real structured records, not generic card grids or a conversation between two agents.

### 6.2 SIRA buyer pages

| Page | Route | Phase | Main content and actions |
|---|---|---|---|
| Buyer setup | `/onboarding/sira` | Foundation | Organization/admin, data policy, manual or connected context, Company Profile review, lightweight Stack, approval and transaction readiness; always allow a manually confirmed first decision |
| Decisions | `/decisions` | First build | New decision, Active by nearest deadline, History by current/superseded version, owner/blocker/checkpoint |
| New decision | `/decisions/new` | First build | Outcome, deadline, incumbent, users/owner/payer, visibility, material intake, live Purchase Brief |
| Need | `/decisions/{id}/versions/{v}/need` | First build | Desired outcome, contract/deadline, stakeholders, only material clarifications |
| Company fit | `/decisions/{id}/versions/{v}/company-fit` | First build | Confirmed company facts, current stack, provenance/freshness, Decision rules, sharing preview, calibration |
| Options | `/decisions/{id}/versions/{v}/options` | First build | Recommendation, stability, aligned Option Matrix, feedback, Ask vendor, evidence frontier |
| Action | `/decisions/{id}/versions/{v}/action` | First build | Selected plan, Review -> Authority -> Execute/assign -> Verify timeline, exact current action |
| Result | `/decisions/{id}/versions/{v}/result` | First build | Verified artifacts, payment/fulfillment/deployment separation, Company-stack consequence, outcome checkpoint; contextual receipt only when money moved |
| Receipt detail | Result drawer; optional `/receipts/{id}` | Foundation | Immutable line items, fee, approval, Prava/merchant/order/entitlement references, print/export |
| Company Profile | `/company-profile` | Later | Private facts, owners, sources, freshness, sharing policy, version history |
| Company stack | `/company-stack` | Later | Tools, jobs, contracts, integrations, owners, dependencies, renewal state, before/after changes |
| Renewals | `/renewals` | Later | Calendar/list, cancellation deadlines, confidence, create/resume decision |
| Outcomes | `/outcomes` | Later | Adoption/value checkpoints, attribution level, open follow-up, private learning |
| Audit | `/audit` | Later | Immutable decisions, versions, approvals, actions, evidence lineage, exports |

#### Decision workspace tabs

The structured canvas follows the five-stage Decision Path: **Need, Company fit, Options, Action, Result**. Evidence, Decision Ledger, Stack Diff, disclosure preview, tasks, history, and versions open as drawers or nested tabs without replacing the current stage URL.

The Options stage uses an aligned semantic table on desktop, never independent marketing cards. Default columns are action/support status, comparable cost, Company-stack change, and next action. Show decision-level stability above the table; raw coverage, evidence, provenance, risk, and math stay in the Ledger. Mobile comparison holds up to three selected options and shows attributes vertically. `NO_ELIGIBLE_SUPPORTED_ACTION` is a dedicated result with evaluated/excluded counts, exact blockers, evidence/category limits, and server-provided safe next actions; it is never an empty table.

### 6.3 SEIL seller pages

| Page | Route | Phase | Main content and actions |
|---|---|---|---|
| Seller setup | `/onboarding/seil` | Foundation | Seller organization, product claim/invitation, private source scope, editor/reviewer roles, first Product Evidence draft and publication readiness |
| SEIL home | `/seller` | Foundation | Products needing attention, claim/review tasks, recent versions, onboarding checklist |
| Product search/claim | `/seller/products/search` | First-build entry | Public-safe search, product identity, authority state, claim or signed-invitation entry |
| Products | `/seller/products` | Later | Product Passport and Product Evidence portfolio, owner, health, state, current version |
| New product | `/seller/products/new` | Later | Chat/source intake, private Product Passport, identity/edition/region, compile first draft |
| Product workspace | `/seller/product-evidence/{product_id}` | First build | Narrow claim/status, Product Evidence editor, health, evidence, fit/anti-fit, review, publish, exports, and activity |
| Version view | `/seller/product-evidence/{product_id}/versions/{version}` | Later | Immutable Pack, authority/verification, current/superseded/suspended state, version diff |
| Sources | `/seller/sources` | Later | Files, URLs, help-center crawl, scope, owner, versions, sync/freshness/conflicts |
| Opportunities | `/seller/opportunities` | Later | Qualified sanitized requests only, status, deadline, owner, no hidden buyer identity |
| Opportunity | `/seller/opportunities/{id}` | Later | Requirement Brief, qualification, allowed missing-field request, anti-fit, plan, positioning, consent |
| Offer | `/seller/offers/{id}` | Later | Engagement-scoped commercial terms, quote/expiry, revisions, merchant chain, fulfillment specification |
| Activity | `/seller/activity` | Later | Measurement window, answer renders, handoffs, observed self-service and privacy thresholds |

#### Product workspace tabs

The full Product workspace uses **Passport, Pack, Evidence, Fit, Publish, Activity**:

- **Passport:** private sources, draft claims, roadmap/capacity, commercial bounds, positioning library, fulfillment, unpublished constraints.
- **Pack:** buyer-safe typed fields only; identity, jobs/segments, capabilities, requirements, compatibility, security/privacy, deployment, limitations, commercial/contract links, fulfillment, merchant chain, operations, and learning policy. Live offers, quotes, contracts, tax, discounts, and availability remain separate versioned objects.
- **Evidence:** source, citation, version, scope, verifier, freshness, dispute/revocation, affected fields.
- **Fit:** fit and anti-fit rules, dependencies, permitted remediation, qualification preview.
- **Publish:** validation, diff, reviewer comments, immutable preview, authority, version history, exports. Publication checks hard-rule evidence/freshness, prohibited positioning, and reviewer separation where policy requires it. Exports show Pack/version, authority, verification summary, generated time, source links, and content hash; they never add claims.
- **Activity:** measurement window, published-answer renders, seller handoffs, and explicitly non-causal **observed self-service**. Never expose individual buyers.

Buyer-specific positioning and offers never live in the product-global workspace or cache. They exist only under an engagement-scoped Opportunity/Offer route, use approved Pack claims plus separately authorized commercial fields, and support `NO_CHARGE`, `FREE_TRIAL`, `FIXED_ONE_TIME`, `FIXED_RECURRING`, `METERED`, `COMMITTED_SPEND`, and `PRORATED_CHANGE`. Keep estimated, authorized, invoiced, charged, credited, and settled amounts distinct.

The first-build route shows only server-backed claim/status, Pack health, typed correction, Evidence, Fit, Review/Publish, Exports, and Activity. Passport, Sources, conversation, Opportunities, and Offers remain hidden until their allowlisted contracts exist; never render fake empty tabs.

#### Seller lifecycle

Render the exact server state and available actions. The flow is not a single line:

```text
UNCLAIMED -> CLAIM_PENDING -> SELLER_DRAFT
                         \-> CLAIM_DENIED -> submit different proof
SELLER_DRAFT <-> VALIDATION_CONFLICT
SELLER_DRAFT -> IN_REVIEW -> CHANGES_REQUESTED -> revised SELLER_DRAFT
                          \-> PUBLISH_READY -> PUBLISHED
                                            \-> PUBLICATION_FAILED
new published version -> prior version SUPERSEDED
```

Suspended, disputed, rejected, and archived views appear only after their contracts exist. Never infer them from another state.

Seller projections exclude hidden budgets, employees, internal strategy, competing offers, prior private failures, unrestricted Company-stack data, named outcomes, and affected-buyer lists. Seller floors and internal approval rules never leave the seller workspace. Contacts appear only after scoped mutual consent. Disable session replay on restricted seller/evidence screens.

### 6.4 Shared settings and internal operations

| Page | Route | Phase | Content |
|---|---|---|---|
| Profile and notifications | `/settings/profile`, `/settings/notifications` | Foundation | Name, locale, accessibility, channel preferences, quiet hours |
| Organization and members | `/settings/organization`, `/settings/members` | Later | Region, domains, legal entities, members, roles, invitations, delegations |
| Connectors | `/settings/connectors` | Later | Catalog, scopes, last sync, health, owner, run history, reconnect/pause/remove |
| Billing and payments | `/settings/billing` | Later | SIRA entitlement, invoices, transaction fee policy, Prava readiness; no stored credential display |
| Security and access | `/settings/security` | Later | SSO/SCIM, sessions, step-up methods, data policy, retention, break-glass contacts |
| Developer | `/settings/developer` | Later | API keys, webhook endpoints, export/syndication; secret shown once |
| Organization audit | `/settings/audit` | Later | Membership, policy, connector, export, and security events |
| Review operations | `/ops/reviews` | Internal | Seller verification, claims, Pack review, evidence and publication decisions |
| Trust operations | `/ops/trust` | Internal | Suspensions, disputes, appeals, merchant/identity mismatches, investigations |
| Provider health | `/ops/connectors` | Internal | Senso, Prava, merchant, fulfillment, identity and connector health/reconciliation |
| Taxonomy and policy | `/ops/taxonomy` | Internal | Category schemas, aliases, gate/risk rule versions, controlled publication |
| Break-glass audit | `/ops/audit` | Internal | Just-in-time access, case, scope, expiry, actions; no ordinary operator bypass |

### 6.5 Role-aware authority

The server filters every projection by tenant, role, purpose, and object. Unauthorized facts, counts, tasks, routes, controls, analytics, and notification content are absent from the payload and DOM, not merely disabled.

| Role | Visible scope | Distinct authority |
|---|---|---|
| Requester/end user | Own request, safe progress, assigned questions, final safe result | Create/edit before lock, answer, provide outcome feedback |
| Decision-maker | Decision rules, allowed company facts, plans, stability, Stack impact | Compare, ask vendor, select plan, accept a policy-permitted exception |
| Policy reviewer | Assigned gate, allowed evidence, expiry | Approve/reject/request evidence/grant defined exception |
| Budget owner/procurement | Comparable TCO, quote/terms, cost center, approval history | Approve or reject exact amount and terms; request revision |
| Cardholder | Approved merchant, line items, exact amount/currency/fee, expiry, payment state | Authorize that payment only; cannot edit the decision |
| Implementer/IT operations | Assigned configuration, migration, deployment, fulfillment, Stack checks | Execute/acknowledge steps, attach proof, report blocker, verify fulfillment |
| Auditor | Authorized immutable versions and lineage | Read/export only |
| Seller editor | Own drafts, Pack health, gaps, evidence, comments | Edit/evidence/submit; no protected self-approval |
| Seller reviewer | Own frozen revision, validation, diff, publisher authority | Request changes, approve, publish, suspend when authorized |

## 7. Signature components

| Component | Required behavior |
|---|---|
| Workspace switcher | Shows only authorized org/workspace combinations; explicit boundary change |
| Object rail | Navigation, recent objects, state/blocker, onboarding; objects are Decisions or Products, not chat threads |
| Conversation thread | Messages, proposed captures, source links, activity summary, safe failure |
| Structured capture | Proposed/confirmed state, source, owner, privacy, validation and version |
| Decision Path | Five stages, current/blocker/completed status, version and last checkpoint |
| Option Matrix | Comparable rows/table, action-neutral plans, separate dimensions, ordinary links/buttons |
| Decision Ledger | Why this action, Evidence, What could change, Audit and math; drawer/full-screen sheet |
| Evidence Mark | Authority separate from verification/freshness: **Published by vendor**, **Compiled by Seilnsara**, or **External, not claimed** |
| Stack Diff | Added, removed, retained, staged and dependency-changed items |
| Execution Timeline | Review, authority, execute/assign, verify; payment is conditional |
| Pack Health | Required/complete/stale/conflict counts with field-linked recovery |
| Review Timeline | Exact revision/hash, reviewer, decision, reason, time, immutable history |
| Privacy Mark | Private, Shared in brief, Published, Restricted; text and icon, never color alone; Restricted appears only to disclosure managers |
| Active operation | Operation, owner, checkpoint, timestamp, safe-to-leave and recovery state |
| Authorized action | Server label, consequence, permission/step-up requirement, idempotent pending state |
| Connector status | Scope, read/write behavior, owner, last success, freshness, health, test/reconnect |

Every Evidence Mark includes: **Publisher authority identifies who stands behind this package; it does not mean every claim was independently verified.** Compiled or external evidence is **Research only**: no seller anti-fit result, plan selection, Purchase Intent, or execution control.

When the current substep exposes exactly one permitted mutation, render it as the filled primary action. If a projection exposes several actions without an explicit primary field, render neutral controls and do not infer priority from list order. Respect `requires_confirmation` exactly.

## 8. Banners, dialogs, drawers, popovers, and notifications

### 8.1 Banners

Banners persist until the condition is resolved unless marked informational.

| Banner | Placement and action |
|---|---|
| Workspace/organization boundary | Top of shell after switch or when acting in an unusual role |
| Demo/fixture/non-production | Global, unmistakable, never styled as production success |
| Terms/privacy update | Global or sign-in boundary; effective date and Review action before consent when required |
| Cookie preference | Public site only when nonessential analytics exist; no nonessential tracking before consent |
| Offline/reconnecting | Global; preserve data and disable unsafe mutation until reconciled |
| Active operation | Object header; operation, checkpoint, owner, timestamp, safe return |
| Decision updated/superseded | Decision header; decisive diff, invalidated authority, Review new version |
| Low coverage/research only | Options; evaluated-universe limits and safe evidence/claim path |
| Unstable/undetermined | Options; exact evidence frontier or missing bound; no unsafe action |
| Authority required/rejected/expired | Company fit or Action; required role, safe reason, assign/revise path |
| Consent declined/expired | Engagement; no contacts revealed, continue privately or choose another option |
| Quote/payment expiry or uncertainty | Action/Result; separate known charge from unknown state, disable duplicate payment |
| Paid-unfulfilled/partial fulfillment | Result; confirmed payment and missing items separately, per-item recovery |
| Claim/review/publication state | SEIL header; pending, denied, frozen, changes requested, ready, failed, superseded |
| Stale/conflicting evidence | Product section and affected fields; owner and revalidation action |
| Connector degraded/revoked | Source-dependent page; last safe sync and reconnect/manual alternative |

### 8.2 Dialogs and sheets

Use a dialog for a consequential choice and a drawer/sheet for detail. Permit one modal layer at a time. Local UI owns only unsaved-work confirmation; server mutations open a confirmation dialog exactly when their action descriptor sets `requires_confirmation=true`.

**Actions that may receive a confirmation descriptor:**

- discard unsaved work;
- change visibility or share the exact Requirement Brief;
- keep/eliminate/ask vendor/need evidence when a reason is required;
- select an exact Action Plan/version/hash;
- record mutual consent or decline;
- approve, reject, delegate, or grant an exception;
- leave for Prava hosted authorization;
- retry an uncertain side effect only when the server permits;
- cancel, request refund, or apply a compensating action;
- submit/withdraw a product claim;
- submit a revision for review;
- request changes, approve, reject, publish, suspend, or create a new Pack version;
- replace evidence that affects claims;
- connect, rescope, pause, or remove a connector;
- invite/remove a member or change a role.

**Drawers/full-screen mobile sheets:**

- Decision Ledger and calculation detail;
- source/citation/evidence detail;
- Company Profile fact and sharing detail;
- Stack Diff and dependency detail;
- calibration result and rule proposal;
- Requirement Brief disclosure preview;
- engagement and both consent states;
- task assignment and approval history;
- payment, fulfillment, receipt, and artifact history;
- Product Passport field history;
- Pack validation gaps, revision diff, comments, publication preview, versions and exports;
- connector scopes, run history, safe errors, and sync detail;
- notification center and activity history.

One overlay manager enforces priority: secure handoff return/status, confirmation, drawer/sheet, then popover. It makes background content `inert`, locks page scroll, gives every overlay an accessible name and visible close control, places initial focus deliberately, and prevents focus escape. Escape closes when safe. Close restores the live trigger; after navigation or an absent trigger, focus moves to the new page heading. Provider return focuses the reconciled status heading. Destructive actions name the object and consequence. Step-up authentication appears immediately before the protected mutation, not at page load.

### 8.3 Popovers, toasts, and browser pop-ups

- Popovers are limited to workspace/account switching, filters, sort, status explanations, citation preview, column controls, and overflow actions.
- Toasts acknowledge low-risk events such as Saved, Copied, Upload queued, Sync started, or Export ready. Approval, publication, payment, failure, suspension, and blocked states are never toast-only.
- OAuth-style connectors may use a user-initiated browser pop-up with a same-tab fallback when blocked.
- Prava uses a user-initiated hosted redirect/window. Returning from it resumes backend reconciliation; the callback alone never displays payment success.
- Browser notification permission is requested only after the user enables that channel in settings; denial keeps in-app/email alternatives and never blocks work.

### 8.4 Notifications

In-app Inbox is canonical. Email is supported for assignments and expiring actions. Slack and Microsoft Teams are optional connectors for safe summaries and deep links. Notifications never contain hidden buyer/seller context, raw evidence, payment credentials, full rejection reasons, or contact details before consent.

Every notification has object, safe event label, required role/action, expiry when applicable, and an authenticated deep link. Users can configure channel and quiet hours, but required security and financial notices cannot be fully disabled.

## 9. Connectors

All connectors use one catalog and detail pattern: purpose, data read/write, scope, owner, authorization method, last successful sync, freshness, health, run history, Test, Reconnect, Pause, and Remove. Never display stored secrets.

| Connector group | Surface | Required design behavior |
|---|---|---|
| WorkOS identity | Security, organization, members | SSO/domain/directory status; IdP membership never implies application authority |
| Senso evidence | SIRA/SEIL Sources | File/text/URL/help-center ingestion, folder scope, version/citation, grants, last sync, denied/revoked/degraded states; retrieved does not mean verified |
| Prava authorization | SIRA Action and billing readiness | Hosted status, expiry and reconciliation only; credential never enters browser or UI |
| Merchant and fulfillment | SIRA Action/Result; SEIL Offer | Certified capability, seller/entity/merchant chain, order vs entitlement, test and reconciliation states |
| Company discovery | Company stack connectors | Generic SSO inventory, expense, contract/invoice, usage, security and admin sources; manual first decision remains possible |
| Seller operations | Product/Offer connectors | Quote, checkout, provisioning, cancellation, refund and support adapters, each separately healthy or blocked |
| Communication | Notification settings | Email core; Slack/Teams optional; minimum safe context and deep links |
| Developer API/webhooks | Developer settings | Scoped key creation/revocation, signing status, endpoint health, delivery/retry history |

Connector states are: Not connected, Setup required, Connecting, Healthy, Syncing, Degraded, Access denied, Stale, Paused, and Revoked. A missing connector lowers confidence or blocks only facts/actions that require it; the UI always offers the manual or deferred path when product policy permits.

Senso source readiness is shown separately as `REGISTERED -> AUTHORIZED -> SYNCING -> PROCESSING -> READY`, plus `DEGRADED` and `AUTH_REVOKED`. Activation requires grant read-back and a negative folder-denial test. Only complete processing makes a source available for compilation; READY still does not mean the source or claim is verified.

Inline connector suggestions may appear after a relevant milestone, such as **Get updates in Slack**, but are dismissible, shown once per context, and never interrupt the primary workflow.

## 10. State and recovery rules

### 10.1 Universal display states

- **Loading:** keep the last safe state and use local skeletons. Name long operations.
- **Empty:** explain why, show one next action, and give a safe example. Never show only **No items found**.
- **Partial:** preserve verified fields, name missing evidence and its effect, block only unsafe actions.
- **Error:** say what is known, what is unknown, whether authority or money was used, and the safest recovery.
- **Success:** show the verified transition, artifact, Company-stack impact, owner, and next checkpoint. No decorative success screen without proof.
- **Unauthorized:** restricted data and controls are absent, not blurred, disabled, or hidden with CSS.
- **Read-only:** explain whether the cause is role, frozen review, superseded version, publication, expiry, or audit mode.
- **Autosave:** show Saving, Saved with time, Offline, and Conflict. Never discard the confirmed server revision.
- **Long-running work:** refresh/reconnect restores operation, latest checkpoint, owner, timestamp, and authorized recovery.

Keep approval, payment, merchant order, fulfillment, deployment, and outcome as separate state families. Likewise, keep Product Evidence lifecycle, evidence verification, freshness, and publisher authority separate. Do not flatten them into a generic success/warning/error value.

### 10.2 Action-specific result proof

| Action | Action path and required proof |
|---|---|
| Reuse existing | Confirm retained capability; Decision record, unchanged Stack, predicted saving, next review |
| Configure existing | Review patch -> authority -> execute/assign -> verify; configuration record, evidence, staged/active Stack update |
| No action | Record reason/owner and next trigger; unchanged Stack |
| Renew/resize | Review contract/quantity/quote -> approve -> charge only if applicable -> verify confirmation, terms, Stack update, and receipt only when charged |
| Cancel | Review dependency-safe exit/data plan -> approve -> submit -> verify cancellation, export/retention/revocation proof, staged removal |
| Buy/replace | Review acquisition/migration -> approve -> charge when applicable -> provision -> verify order/receipt when charged, entitlement, deployment, migration/retirement, Stack patch |
| Consolidate | First-build render-only specimen; show sequence and proof shape but no selection/start control or implied execution |

Zero-charge paths start the action run directly and omit Purchase Intent, Prava, payment states, transaction fee, and receipt. A workflow completion flag without the action-specific artifact is not Result proof.

### 10.3 Approval, payment, and fulfillment

| Purchase state | Required treatment |
|---|---|
| `AWAITING_APPROVAL` | Show exact locked intent, roles, and expiry; no payment control. |
| `APPROVED_NOT_STARTED` | Show approved merchant/amount/version and the server action to begin cardholder authorization. |
| `PAYMENT_IN_PROGRESS` | Show provider checkpoint/time; disable duplicate starts and show safe-to-leave only when projected. |
| `PAYMENT_NOT_COMPLETED` | Distinguish declined, expired, and failed; state that no successful charge is confirmed; retry only when authorized. |
| `PAYMENT_UNCERTAIN` | Preserve known facts, block duplicate checkout, and expose reconciliation/escalation only. |
| `PAID_UNFULFILLED` | State that payment is confirmed while entitlement is missing; expose provisioning, support, or refund recovery. |
| `PURCHASE_FULFILLED` | Show immutable receipt and verified entitlement; deployment and outcome remain separate. |
| `REFUND_PENDING` / `REFUNDED` | Show original charge, expected/settled credit, timestamps, open items, and Stack/entitlement consequence. |

Session expiry, provider decline, unknown checkout, reporting failure, partial fulfillment, and return from hosted authorization always resume backend reconciliation. A browser callback never declares success. Deployment uses Not started, Staged, and Active; outcome checkpoints remain separate from all transaction states.

## 11. Accessibility and content

- Meet WCAG 2.2 AA; text contrast at least 4.5:1 and control/focus contrast at least 3:1.
- Use a visible 2-pixel focus ring with 2-pixel offset, skip link, landmarks, logical headings, and semantic tables/lists.
- Route changes focus the page heading. Drawers/dialogs trap and restore focus.
- Status always has text and, where useful, an icon. It remains legible in Windows forced-colors mode.
- Reflow at 200% and 400% zoom. All primary actions remain reachable at 320 px.
- Respect reduced motion. Do not make the entire chat or page an ARIA live region.
- Use ordinary links for navigation and buttons for mutations. Never infer stage completion or permission from the URL.
- Primary copy is plain and factual: **Could change if...**, **Published by vendor**, **Payment confirmed; access still missing**.
- Avoid “AI-powered,” “magic,” “perfect fit,” “best on the market,” and unsupported savings or deflection claims.
- Always say **best supported action among evaluated options** and disclose low coverage.

## 12. Implementation acceptance checklist

- Shared landing and `/home` treat SIRA and SEIL as peers.
- Each workspace uses its own wordmark, accent, nouns, routes, cache, and server-authorized projection.
- Object pages use the rail + structured canvas grammar; conversation is added only where its contract exists and becomes the third pane on wide screens.
- Chat proposals are visually distinct from confirmed/versioned records.
- Authorized disclosure managers see private/shared/published/restricted state; everyone else receives no restricted field or marker.
- Every surfaced First-build or Foundation page renders loading, empty, partial, blocked, expired, error, read-only, and success where applicable.
- Every side effect uses the exact server-provided action, version/hash, pending state, and recovery.
- Banners, dialogs, drawers, notifications, and connector states follow this document.
- Desktop, tablet, mobile, 320 px, 200/400% zoom, keyboard, screen reader, reduced motion, and forced colors are tested.
- No dark-mode code, toggle, token set, or dark screenshot is shipped.
- No Jack & Jill copy, characters, emojis, exact visual trade dress, or recruiting metaphors are reproduced.
