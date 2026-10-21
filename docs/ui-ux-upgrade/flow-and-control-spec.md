# Flow, business-context, and control specification

Version 1.0 · 21 October 2026 · Proposed implementation specification

Companion to the [implementation plan](../../sira_seil_ui_ux_implementation_plan.md) and [design playbook](../../sira_seil_ui_ux_synthesis_driven_design_system.md). This is the starting specification for tasks 01, 03, and 05–11. Current executable contracts remain authoritative; proposed projections, roles, connectors, or actions need implementation before appearing as available.

## 1. End-to-end flow inventory

Every flow needs a happy path, meaningful first value, persistent return point, and failure recovery. Copy namespaces refer to the [copy specification](copy-spec.md); implementations may add stable state-specific keys.

| ID | Entry and job | Primary artifact / proposed controls | Exit and exceptional states | Plan / copy |
| --- | --- | --- | --- | --- |
| **F01** | Visitor understands the product and chooses a side | Audience-specific public narrative; buying/selling CTA; how-it-works; category/capability coverage | Correct workspace/auth destination; unavailable capability explained; no misleading CTA | 02, 12 / `public.*` |
| **F02** | User enters or returns to the intended workspace | Sign-in, supported guest path, account/party identity, return destination, verification/step-up | Correct organization/party; denied access, expired session, wrong account, provider failure; preserve allowed draft/intent | 05 / `auth.*` |
| **F03** | User provides or corrects decision-relevant business context | Fact list/editor; source/owner/date/version; inferred/confirmed/unknown presentation; change reason; retire where supported | Context saved as a new valid version; conflicting edit/source shown; affected missions identified | 01, 05, 10 / `company.*` |
| **F04** | New or returning user starts/resumes a mission | Outcome composer; relevant starters; mission header; real work summary; open tasks and artifacts | Durable mission and next step; no historical activity, unavailable runtime, resumable provider failure | 06 / `mission.*` |
| **F05** | Buyer and SIRA establish the brief and delegation scope | Editable goal, required outcome, MUST/SHOULD/COULD, quantity/usage, timing, selected context, private limits | Confirmed version and mandate; required fact missing; proposed criterion/policy change with impact review | 06 / `brief.*` |
| **F06** | SIRA discovers and evaluates eligible options | Actual work status; coverage; source origin; product edition; current/stale/research-only facts; refresh | Candidate/evaluation artifact; partial research, provider error, no candidates, expired observations, conflict | 06 / `research.*` |
| **F07** | Buyer compares and chooses a defensible next step | Requirement-led comparison; total commitment; expected/high usage where relevant; effort/trade-offs; keep-current/defer/no-fit | Saved comparison/selection or explained no-fit; unverified fact cannot become proven pass/fail | 06, 11 / `comparison.*` |
| **F08** | Buyer inspects support or corrects evaluation | Source detail, exact claim/scope/date; keep/eliminate/need evidence/ask vendor; criterion change preview | Recorded feedback or new brief/evaluation version; no hidden ranking-policy mutation; unreachable or withdrawn source | 06 / `evidence.*`, `brief.*` |
| **F09** | Seller registers a product and prepares evidence privately | Product/edition identity; ownership/capability status; claim/source editor; source attach/import; fit/anti-fit | Private draft; unsupported format, duplicate source, missing claim, ownership denied, conflicting edition | 07 / `seller.*` |
| **F10** | Seller reviews and publishes an exact revision | Claim/source diff; gap list; review submission; requested changes; permitted release preview; publish | Reviewed immutable public version; changed-under-review, publication failure, superseded/withdrawn state | 07 / `seller.*`, `release.*` |
| **F11** | Seller evaluates a released buyer need | Party-safe requirement view; published evidence links; fit / anti-fit / needs-info response | Useful supported response; insufficient scope, stale qualification, no fit, more information needed | 08 / `qualification.*` |
| **F12** | Each party decides whether to share contact and be introduced | Recipient and exact field preview; purpose; own consent status; expiry; other-side wait status within policy | One qualified introduction after current dependencies and valid consents; decline/expiry/change/revocation | 08 / `consent.*` |
| **F13** | Parties exchange exact commercial terms | Buyer offer form; line totals; scope/commitment/expiry; seller accept or one counter; term diff | Agreement pending required approval; version conflict, expired term, unsupported extra negotiation | 09 / `offer.*` |
| **F14** | Authorized human reviews a protected action | Exact object/version/terms, consequence, required role, conditions/expiry, verification, supported approve/reject paths | Recorded applicable approval; denied authority, rejection/revocation/expiry where supported, superseded scope | 08–09 / `approval.*` |
| **F15** | User performs a supported external handoff and follows outcome | Destination/recipient/amount/reference; approved version; prepare/open; persisted receipt; outcome task | Ready/opened/expired/unknown are explicit; purchase/provision/deployment separately attributed | 09 / `handoff.*`, `outcome.*` |
| **F16** | User sees what needs judgment and resumes work | Inbox groups, reason/owner/deadline, direct artifact route, factual change summary | User resolves a real need or knows who is waiting; no invented progress or notification delivery | 06, 08, 14 / `inbox.*`, `mission.*` |
| **F17** | Authorized user connects, reviews, syncs, or revokes a capability | Purpose/scope/account preview; provider consent; health/sync detail; correction/reconnect/disconnect | Verified capability or explicit not-ready state; partial/revoked/expired/wrong-account/rate-limit recovery | 10 / `connection.*` |
| **F18** | Team revisits a tool or a different buying category | Current facts/contract; prior decision; new outcome/criteria; category evidence/cost/action lens | Fresh mission with category-supported next step; unsupported renewal/migration/ordering remains preparation | 11 / `lifecycle.*`, `category.*` |

### Flow specification template

For each flow, record: job, actor/organization/party, entry/deep link, selected context, source of truth, state transitions, layout, copy keys, primary/secondary action, server command/preconditions, visibility, success receipt, failure/recovery, return point, event signals, and scenario checks. A flow may use multiple backend workflows; do not invent one global state machine.

### Shared state presentation

| State family | Required presentation and behavior |
| --- | --- |
| Empty | Explain what belongs here and offer a supported first action; no fake activity or vendor records |
| Loading / running | Show actual operation phase/state, last update where available, and supported navigation/cancel behavior |
| Partial | Show completed useful work and explicitly missing data; prevent an incomplete result from looking definitive |
| Needs human | State what is needed, why, who can act, current scope, and the consequence of acting |
| Blocked / denied | Name the missing authority, fact, capability, or policy condition and a supported next step |
| Stale / superseded | Keep the historical object readable; show current version and changes before a consequential action |
| Conflict | Show conflicting values/sources and how to resolve; do not silently select a convenient value |
| Retryable error | Preserve inputs; explain whether an effect occurred or is unresolved; retry only with valid semantics |
| Unknown / uncertain | Reconcile authoritative state; don't offer a fresh duplicate mutation or declare external success |
| Confirmed result | Show authoritative receipt, exact scope/version, what remains external, and the next owner |

## 2. Business context and company memory

### Field catalog

Every fact needs value and meaning, not just a text blob. Where current payloads cannot express required metadata reliably, add typed validation/projections before exposing the feature.

| Context group | Initial facts | Why the decision needs them | Default visibility / current-kind mapping |
| --- | --- | --- | --- |
| Organization basics | Verified organization identity; team/department; operating location where relevant | Ownership, availability, role and billing context | Party-private; `NOTE` or validated identity source |
| Business outcome | Problem, desired workflow/result, timing, affected team | Frames the mission and useful alternatives | Buyer-private until permitted release; `REQUIREMENT` |
| Existing stack | Product/edition, owner, known seats/usage, integration/identity environment | Compatibility, duplicate capability, keep-current/build/buy choices | Buyer-private; `STACK` |
| Requirements | Capability, priority, threshold/unit, scope, acceptance evidence | Eligibility and later adoption checks | Buyer-private; approved subset released; `REQUIREMENT` |
| Constraints | Region, data handling/retention, deployment, contractual limits | Hard exclusion or review requirement | Buyer-private; approved subset released; `CONSTRAINT` |
| Preferences | Usability, support, vendor profile, preferred workflow | Trade-offs after eligibility | Buyer-private; `PREFERENCE` |
| Commercial assumptions | Budget/ceiling, quantity, usage scenarios, horizon, currency, taxes known/unknown | Comparable cost and approval context | Buyer-private; validated `CONSTRAINT`/`POLICY` payloads |
| Procurement policy | Spend/access thresholds, reviewers, exceptions, approval conditions | Who may authorize the proposed action | Buyer-private; `POLICY` |
| Contract/lifecycle | Existing commitment, end/notice date, renewal owner, confirmed terms | Renewal, replacement, migration and timing | Buyer-private; validated `STACK`/`NOTE` until a dedicated contract exists |
| Success and adoption | Expected benefit, test criteria, implementation owner, outcome checkpoint | Establishes whether buying resolved the original need | Party-private; `REQUIREMENT`/`NOTE` |
| Seller identity/authority | Product ownership, editor/reviewer/commercial permissions | Determines who can assert, publish, or commit | Seller-private; authoritative role/ownership records |
| Seller product knowledge | Edition, capabilities, scope, evidence, fit and anti-fit | Reusable accurate response to qualified needs | Seller-private drafts; reviewed buyer-safe publication |
| Seller commercial context | Allowed pricing, concessions, floor, negotiation authority | Prepares an authorized response | Seller-private; never a shared marketplace field |

The listed kind mappings are implementation starting points. Avoid duplicating existing seller product/evidence records into buyer company-memory storage. Private commercial inputs need validated exact values and cannot override protected actions.

### Fact lifecycle and use rules

1. **Capture:** identify user-provided, connected, public-research, or inferred origin.
2. **Attribute:** record source/account, owner, observation/confirmation date, version, purpose, and visibility where supported.
3. **Clarify:** show unknown, inferred, confirmed, stale, or conflicting as presentation distinctions; do not invent current backend enums to match these labels.
4. **Select:** make mission-relevant context explicit. Do not inject every available private fact into every model call or public search.
5. **Apply:** requirements/policy affect evaluation through server validation; a user preference or imported text cannot grant authority.
6. **Change:** persist a new version with a reason; identify impacted active missions and re-evaluate through supported contracts.
7. **Retire/disconnect:** separate stopping future sync, excluding a fact from future decisions, retention/deletion policy, and preservation of historical decision evidence.

Conflicting manual and synced facts require visible resolution and provenance. “Connected” is not “confirmed by the company,” and “recently synced” is not “commercially current.” A directory headcount may not equal paid seats or required licenses.

### Business-decision register

Record owner, decision, evidence, allowed wording/behavior, and review trigger for:

- Target first category and supported purchase path.
- Platform fees, vendor fees, and ranking/commercial-neutrality policy.
- Supported currencies/geographies and tax/FX treatment.
- Team membership and exact authority/routing rules.
- Contact release, reviewer visibility, data retention/deletion, and supported export.
- Notification channels, follow-up consent, escalation, and response expectations.
- Which external provider can confirm purchase, activation, delivery, or deployment.

Where unknown, use a truthful bounded flow: research/preparation, manual context, explicit external task, or unpublished pricing. Do not invent a business policy to finish a screen.

## 3. Human-in-the-loop interaction contract

### Action/authority matrix

This matrix defines desired UX questions. Actual authorization must map to current server capabilities; some paths need additional backend support.

| Action | Human role / authority source | Review content | Agent behavior and authoritative result |
| --- | --- | --- | --- |
| Read/research within mission | Valid principal, data access, bounded mandate | Research scope and selected context | Proceed within limits; record actual sources/work; ask only if the next material decision needs input |
| Correct a private brief/context fact | Authorized editor of that object | Changed field, reason, evaluation impact | Propose or apply through supported command; new version confirms the change |
| Change company policy | Authorized policy owner/capability | Affected rule and missions; difference from local preference | Agent proposes; protected command validates and records exact change |
| Publish seller evidence | Eligible editor/reviewer/publisher according to workflow | Exact revision, gaps, diff, buyer-safe content | Prepare and validate; server records approved published version |
| Release a requirement or other data | Authorized disclosing party | Recipient, purpose, exact fields, source revision | Release only permitted projection; persisted release record |
| Respond fit/anti-fit/needs info | Authorized seller participant | Released need, evidence scope, limitations | Draft supported response; record current response without leaking private context |
| Consent to introduction | Required authorized participant on each side | Exact contact fields, recipient, purpose, expiry | No disclosure before valid required consent and current dependencies; deduplicated introduction |
| Accept/counter exact commercial terms | Correct party and supported commercial authority | Exact terms/version, differences, expiration | Follow party-owned commands; agreement remains separate from purchase approval |
| Approve purchase/handoff | Required human approval/execution capability | Amount, recipient, commitment, conditions, version/hash, consequence | Suggest and explain; server rechecks identity, scope, current state, and expiry |
| Connect company data | Provider account and required user/admin consent plus tenant authority | Provider/account, purpose, exact access, data use, revocation | Start supported authorization; show verified granted scope and sync status |
| Execute runtime tool or deployment | Trusted tool policy, scoped principal/grant, environment authority | Specific target/action, data, read/write consequences, limits | Run only available authorized tool; record effect/receipt or unknown result |
| Confirm external outcome | Supported provider evidence or attributed human report | What is confirmed, source, time, remaining gaps | Preserve distinction between self-report, provider confirmation, and assumption |

### Interruption design

Every request for human attention must answer: **What do you need? Why now? What changes if I act? Who is allowed? What happens if I wait or decline?**

Use existing attention kinds deliberately:

- `question`: a required fact that changes the next step; allow unknown/defer only if valid.
- `choice`: alternatives with clear consequences; do not disguise an authority grant as a preference.
- `approval`: exact proposed object and scope; separate review from committing an effect.
- `credential`: route to supported secure authorization; never collect raw secrets in conversation.
- `blocked`: name the dependency and next owner or supported recovery.

Group safe reads and private preparation inside the agreed mandate. Do not ask again for unchanged scope when an existing authorization remains valid. Re-review when material scope, recipient, object version, policy, or authority changes as required by that workflow.

### Required review anatomy

Heading naming the action; object and party; version/currentness; recipient/target; exact content/terms/scope; important consequences and unknowns; required actor; expiry; explicit primary verb; supported change/decline path; pending state; authoritative receipt or reconciliation state.

Do not claim a universal undo. Delivered disclosures cannot be made unseen; a disconnect may stop future access without deleting previously retained evidence; external purchase cancellation depends on its actual provider/contract.

## 4. Integration architecture and experience

### Distinguish six integration meanings

| Type | Example | What it establishes | What it does not establish |
| --- | --- | --- | --- |
| Authentication | Google sign-in through the current auth provider | User identity under the implemented auth policy | Workspace business-data access or spend authority |
| Company-data connector | Authorized suite/identity/usage read | Access to specific provider resources | Full license, contract, billing, or private-company knowledge |
| Product compatibility evidence | Vendor claims integration with a suite | A scoped claim with supporting evidence | That this company has connected or tested the integration |
| Agent runtime capability | A registered API/MCP tool | A particular callable operation under policy | General permission to execute all provider actions |
| Notification delivery | Verified email/Slack/Teams channel | Supported delivery to a configured destination | That saved preferences guarantee successful delivery |
| Transaction/fulfillment integration | Payment/procurement handoff or provider events | The exact confirmed external state | Purchase, deployment, delivery, or adoption beyond that evidence |

### Capability lifecycle

Represent conceptually: unavailable → configured → authorizing → connected → syncing → usable. Also expose partial/degraded, authorization expired/revoked, wrong account, disconnected, and result unknown where relevant. Map to or extend the actual `ConnectorView` and `CapabilityView` contract rather than silently treating these words as existing enums.

**Connection record:** tenant/party, provider and connected account, use case, granted permissions, consent actor/time, supported resources/actions, sync status, last success, source freshness, errors, revoke/reconnect policy, and server-controlled credential reference. Tokens and secrets stay out of UI payloads, logs, copy catalogs, and model context.

**Before authorization:** show the concrete business value and exact data/action scope; allow continuing with manual context when feasible.

**After authorization:** verify account/organization binding and granted permissions before marking a capability usable. Display the last successful retrieval separately from the OAuth callback. Partial grants or provider limits restrict available actions.

**On sync:** read bounded needed data, preserve provenance, validate/normalize, detect conflicts, update a new attributable context version, and notify affected missions when relevant. Provider network I/O and durable commit semantics follow the existing architecture.

**On disconnect:** stop future access/retries, revoke where supported, explain retained/deleted data according to policy, disable dependent actions, and preserve appropriate historical decision records. Failed revocation and local disconnection may need different status.

### Provider work packages

| Package | First useful outcome | Must resolve before enabling | Verification |
| --- | --- | --- | --- |
| Google Workspace read context | A specifically defined company/identity fact used in a buying brief | Exact API/resource/scope, appropriate user/admin authority, account binding, app consent requirements, storage/retention | Real test tenant; denied/revoked/partial scope, wrong account, sync and reconnect |
| Microsoft 365 read context | Equivalent defined fact where Graph supports it | Delegated versus application permission, admin consent, tenant binding, required resource access, field parity | Real test tenant; authority, revoked token, partial data, sync and reconnect |
| First notification channel | A real human-action request reaches its configured owner | Provider, destination, permission, private payload, preference/quiet-hours semantics, retry/deduplication | Delivery and failure evidence with artifact deep link |
| API/MCP runtime action | One explicitly bounded useful operation | Trusted tool registration, auth/authorization, scopes, version, data boundaries, environment, idempotency/recovery | Read/write consequences, denied authority, untrusted output, failure/unknown result |
| Transaction/fulfillment provider | A verifiable next state beyond the current external handoff | Actual provider contract, object mapping, approval scope, event trust, reconciliation, refunds/cancel/receiving if in scope | Duplicate/delayed/out-of-order evidence, timeout, external failure, correct outcome labels |

Use official provider documentation during implementation: [Google Workspace authorization overview](https://developers.google.com/workspace/guides/auth-overview), [Directory API scopes](https://developers.google.com/workspace/admin/directory/v1/guides/authorizing), [Microsoft Graph permissions](https://learn.microsoft.com/en-us/graph/permissions-overview). These support the need for use-case-specific permission design; they do not approve any scope or establish a working integration in this repository.

## 5. Shared UI element inventory

| Surface | Required elements | Important behavior |
| --- | --- | --- |
| Public pages | Audience navigation, clear hero, buyer/seller CTA, real walkthrough/proof, category and capability descriptions, FAQ/footer | Working destinations; claims match release; responsive text and accessible links |
| Mission | Organization/party/agent, goal, state/version/privacy, next need, work summary, artifact, optional conversation | Stable deep link and resumption; factual changes; active surface owns task |
| Brief/context | Labeled fields, priority/unknown controls, source metadata, private indicator, change impact | Draft retention and correction; no hidden policy/disclosure mutation |
| Comparison | Criteria/option headers, evidence cells, consistent cost basis, trade-offs, selected set, next actions | Stable reading order; clear unknown/conflict; responsive detail/scroll alternative |
| Evidence | Claim, source class/link/span, date/version/scope, freshness/conflict, supported next step | Source inspection and return focus; inaccessible source does not become verified proof |
| Seller workbench | Product/edition, claim/source mapping, gaps, fit/anti-fit, revision diff, reviewer, release preview | Draft/public separation; exact review; supported formats and errors |
| Inbox | Reason, owner, mission, consequence, deadline/expiry, next action, wait group | Useful priority; material updates; no invented channel delivery or SLA |
| Release/consent | Exact recipient and fields, purpose, version, consequence, expiry, confirm/change | Server-bound scope and recorded result; no disclosure before authorization |
| Offer/approval | Exact terms/diff, authority, conditions, expiry, scoped primary action | Currentness recheck; correct actor; clear pending/denied/uncertain result |
| Connection | Purpose, provider/account, scope, status/sync detail, permissions, reconnect/disconnect | Account identity separate from connection and capability readiness |
| Outcome | Receipt, confirmed scope, source, external unknown, next owner/task | No claim beyond observed evidence; historical record remains inspectable |

Each element inherits shared loading/error/focus/keyboard/responsive behavior from step 04 and task-specific copy from the content catalog. Final component extraction follows reuse and responsibility, not a mandate to create a component for every table row.
