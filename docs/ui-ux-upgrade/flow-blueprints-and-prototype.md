# Step 03 flow blueprints and structural prototype

Status: design proposal; not tested with representative users. Date: 2026-10-21. Uses the Step 00 capability register, Step 01 object/authority model, F01–F18 in the [flow and control specification](flow-and-control-spec.md), and conditional copy in [copy-spec.md](copy-spec.md).

## Design basis

UI/UX Pro Max searches returned an “Accessible & Ethical + Minimalism & Swiss Style” recommendation for B2B services, with a feature-rich showcase for public pages and a sales-intelligence dashboard pattern. Its web-form guidance calls for labeled fields, inline errors linked to inputs, a focusable linked error summary after failed submit, and explicit loading/success/error feedback. Apply these as reference guidance; our priority hierarchy remains: evidence and business action first, visual polish second. Avoid unverified data-heavy dashboards and decorative effects that compete with trust state.

### Two approaches considered (hypotheses, not observed preference)

| Job | Conversation-led | Artifact-led with optional conversation | Proposed prototype default / reason to test |
| --- | --- | --- | --- |
| Intake | Agent asks sequential questions and builds brief in chat | Brief fields show current value, source, priority and unknown; chat can add/edit | Artifact-led. Users need to correct several fields, compare revisions, and see what will be released. Test whether field-first feels like paperwork. |
| Comparison | Agent narrates one option at a time | Stable criteria-by-option matrix with evidence/gap/source and a short summary | Artifact-led. A comparison must remain scannable and be shareable; narration alone creates working-memory burden. Test narrow layout and assistive technology. |
| Seller evidence | Chat interview followed by hidden draft | Claim/evidence editor with private/published status, source review, revision diff and optional chat extraction | Artifact-led. Seller must inspect exact claims and audience before publication. Chat can accelerate extraction but cannot skip review. |
| Approval | Conversational “approve?” prompt | Dedicated review of exact object/version, terms, authority, consequence and next state | Dedicated artifact/action panel. Conversational approval is too easy to confuse with a preference or casual acknowledgment. |

Evaluation tasks: task completion, time to first useful artifact, corrections before release, comprehension of evidence/uncertainty, field-level correction count, action consequence recall, and next-owner clarity. Do not select the final approach based on internal opinion; user sessions are a Step 03.6 dependency.

## Five service blueprints

### A. Research-only buyer decision (F01–F04, F08, F12)

| Stage | Buyer sees/does | Agent and service work | Durable state / authority | Wait, failure and recovery |
| --- | --- | --- | --- | --- |
| Enter | Open SIRA or return to a mission; state goal or choose a starter prompt | Confirm buyer workspace; read only accessible context; create a draft mission when the supported command is invoked | Buyer mission, brief version, selected context-version IDs | Auth/session failure retains return path; guest/demo content visibly marked. |
| Shape need | Review outcome, MUST/SHOULD/COULD requirements, limits and unknowns; edit fields | Ask only for facts that change evaluation; distinguish user fact, imported/observed fact and assumption | Versioned private brief; change reason and idempotency for mutations | Missing exact unit/time/currency stays unknown; field errors link and focus; stale edit reloads before overwrite. |
| Research | Choose catalog reuse or public-web refresh | Query bounded sources; validate/record consulted source references; present source/freshness | Product and versioned observation records, linked to decision artifacts | Provider unavailable: keep existing brief/results, show no new result; retry with same query after status check. |
| Compare | Inspect same criteria across candidates, source class/date, gaps and trade-offs; correct a requirement | Evaluate evidence against declared criteria; do not turn unknown into pass; avoid unsupported price/currentness | Decision version, criterion results, source refs and feedback | No eligible options: explain blocking criteria and offer safe edits; no fabricated winner. |
| Choose next step | Keep, request evidence or stop; see any consent/release scope separately | Create only the selected supported workflow action | Candidate action / request / artifact with actor and idempotency | If action state is unknown, fetch/reconcile current artifact before retry; preserve selected option. |

### B. Seller evidence publication (F05–F07, F15)

| Stage | Seller sees/does | Agent and service work | Durable state / authority | Wait, failure and recovery |
| --- | --- | --- | --- | --- |
| Enter | Sign in to SEIL; search existing products or add a product by name/URL | Verify seller identity and tenant; research only public sources when asked | Seller-owned product draft; public research observations remain separately labeled | Without configured seller auth, allow public exploration but do not report a saved draft. |
| Prepare | Review claim, source, date, scope, confidence, fit/anti-fit and missing evidence | Extract candidate facts into draft; preserve source refs; treat page instructions as untrusted data | Private evidence pack, source versions and evidence spans | Unsupported or stale claim stays a gap; source fetch failure retains draft and allows correction. |
| Review | Compare exact new revision with current published version; inspect buyer-safe projection | Validate required fields and allowlist; show sensitive/internal fields excluded | Review command/status with reviewer actor; version/hash binding | If source/current revision changed, invalidate review and ask reviewer to inspect current version. |
| Publish | Authorized reviewer confirms exact preview and public audience | Commit approved projection atomically with catalog update | Published evidence version and catalog observation; explicit publisher/time | Failure does not partially publish; retry uses idempotency and reloads actual status. |
| Maintain | See freshness, buyer-facing impact and suspend/revise option | Refresh/mark outdated under actual source policy; no silent rewrite of history | New observation/version; withdrawal state when suspended | Withdrawal affects future catalog access; explain cached or already shared copies per policy. |

### C. Qualified introduction / mutual consent (F08–F10)

| Stage | Party sees/does | Agent and service work | Durable state / authority | Wait, failure and recovery |
| --- | --- | --- | --- | --- |
| Request | Buyer selects a candidate and reviews seller-safe need | Build allowlisted requirement release with recipient, purpose and expiry | Release record and exact brief version | Missing/expired/incomplete brief blocks release with field-level repair route. |
| Respond | Seller sees only released information; passes, requests evidence, or responds | Validate seller organization/actor and record response | Seller response, engagement state and evidence request | No response is not a pass; deadline/SLA only if configured. |
| Consent | Each required party previews contact fields and purpose | Validate consent is current and mutually sufficient; no contact disclosure before all required consents | Versioned consent records with participant, scope, purpose and expiry | Decline/expiry revokes pending transition; changed fields require new consent. |
| Introduce | Both parties see next owner and permitted contact details | Create idempotent introduction only after required consent | Qualified introduction reference | Duplicate requests return existing reference; failed/unknown status reconciles before resubmit. |

### D. Exact offer, approval and external handoff (F11–F13)

| Stage | Buyer/seller sees/does | Agent and service work | Durable state / authority | Wait, failure and recovery |
| --- | --- | --- | --- | --- |
| Offer | Seller prepares exact versioned terms; buyer sees differences and expiry | Enforce party ownership and supported offer transitions | Offer version, amount/currency/line items/conditions | Changed terms create a new reviewable version; accepted agreement is still not spend approval. |
| Plan | Buyer reviews recommendation, exact intent and expected action | Build immutable intent only from supported, current decision/offer terms | Purchase intent with source decision and exact terms | Stale input blocks lock with current artifact link. |
| Approval | Authorized approver reviews spend, recipient, term hash, policy basis and consequence | Verify current authority/policy/version; request step-up if route requires | Approval request/result bound to intent | Denial/expiry/version change blocks execution; show why and who owns next action. |
| Handoff | Authorized executor sees exact amount/currency/payee/reference/expiry and opens merchant HTTPS destination | Create/open handoff; never collect card data or claim charge | Handoff READY/OPENED/EXPIRED/CANCELLED | Failed launch or unknown result triggers status fetch, not a duplicate purchase. Outside merchant completion remains unknown. |
| Outcome | Owner records human-reported or provider-evidenced result, source and date | Keep source classes and state provenance; no synthetic completion | Outcome checkpoint; NOT_MEASURED/INCONCLUSIVE remain valid | Missing confirmation remains unknown; reconcile before retry or closing mission. |

### E. Connected company context refresh (F16; future integration dependency)

| Stage | User sees/does | Agent and service work | Durable state / authority | Wait, failure and recovery |
| --- | --- | --- | --- | --- |
| Select use | Choose a specific fact and business benefit; manual context remains available | Map the use case to provider resources and minimum scopes | Proposed connection record and scope | Current release has no verified suite connection; show unavailable/manual path. |
| Authorize | Inspect provider account, actor/admin requirement, fields, purpose and revoke path | OAuth callback binding, state/nonce validation, secure token storage and scope verification (future implementation) | Tenant/account-bound connection and consent evidence | Denied/wrong account/partial scope does not become connected; preserve manually supplied fact. |
| Sync | Review returned facts, dates, source and conflicts before using them | Bounded read, validation, provenance, partial failure handling | Attributed context version with source/sync timestamp | Provider error/expired token retains last known value with stale marker; reconnect or retire as supported. |
| Disconnect | Confirm future access stops and what retained history policy says | Revoke where supported, stop retries, disable dependent capabilities | Disconnected/revoked state and appropriate audit record | Failed provider revoke is distinct from local disconnect; no deletion guarantee without policy. |

## Navigation and continuity proposal

| Workspace | Primary destinations | Route/deep-link behavior |
| --- | --- | --- |
| SIRA | Work (current mission), Decisions, Inbox, Products, Company | `/sira` remains current home; decision detail preserves request/version/stage; `/sira/decisions` alias remains resolvable. Product search/evidence needs buyer-readable route before adding a new path. |
| SEIL | Work (current seller task), Products, Inbox, Opportunities (only when enabled), Company | `/seil` remains current home; `/seil/products/search`, `/seil/inbox`, and product evidence routes remain. Existing `/seller/*` aliases continue to redirect. |
| Public | How it works, For buyers, For sellers, Pricing, Security, Privacy, Terms | CTAs preserve audience/return destination through sign-in. Pricing/security/legal links stay until accountable policy review clears content. |

Back/return always means “return to the last authorized artifact and current version.” After login, redirect to a validated local return target, preserving decision/product ID but rechecking tenant, actor and current version server-side. Do not bounce legacy `/inbox`/`/settings/profile` to the public homepage if the link has a role-specific destination; preserve the path's intent or render a safe chooser in the routing implementation step.

## Wide and narrow structural prototype

These are layout structures, not finished visual mockups. Do not add a persistent 3-column layout at narrow widths.

### SIRA decision (wide ≥ 1200 px)

```text
┌ Workspace nav ───┬ Mission header: goal · owner · state/version · privacy ─────┐
│ Work             ├──────────────────────────────┬──────────────────────────────┤
│ Decisions        │ Decision artifact            │ Evidence inspector           │
│ Inbox            │ criteria × options            │ source / date / scope         │
│ Products         │ known / missing / conflict    │ why it matters / open source  │
│ Company          ├──────────────────────────────┴──────────────────────────────┤
│                  │ Next action · actor · consequence · optional conversation    │
└──────────────────┴────────────────────────────────────────────────────────────┘
```

### SIRA decision (narrow ≤ 640 px)

```text
┌ Menu · SIRA · task status ─────┐
│ Mission title + version/privacy │
│ Summary / next-owner state      │
│ Criteria list (expand details)  │
│ Option card → evidence sheet    │
│ Source, date, gap, fit reason   │
│ Fixed bottom primary action     │
│ Conversation opens as a section│
└─────────────────────────────────┘
```

The narrow view reorders the same data into a readable sequence, retains labels and comparison context, uses a full-screen evidence sheet with return focus, and never hides an approval consequence behind horizontal scrolling. Any sticky action must leave content and keyboard focus unobscured.

### SEIL evidence review (wide and narrow)

Wide: product identity/status header → claim/evidence table with source inspector → private/public projection preview → revision diff and reviewer action. Narrow: product header → one claim card at a time with source/open and gap state → preview screen → exact revision review → publish/suspend action with audience and consequence. Draft/private versus published state stays visible in both layouts.

## Step 03 validation and open work

- Flow inventory F01–F18 already appears in the companion spec; these blueprints connect five critical journeys to agent actions, durable objects, authority and recovery.
- The proposed artifact-led pattern is a hypothesis. No concept test or accessibility walkthrough with representative users has run.
- Confirm whether current inbox, products and company destinations match user language; keep legacy aliases until route tests approve a migration.
- Visual tokens, component states, responsive implementation and real keyboard/screen-reader checks belong to Steps 04–13. Prototype comprehension is blocked on participant access.
- Do not implement a suite connection, outbound notification or automatic purchase based on the future connected-context blueprint; current contracts do not support those effects.
