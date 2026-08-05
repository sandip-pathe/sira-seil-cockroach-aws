<!-- /autoplan restore point: C:\Users\sandi\.gstack\projects\siel-n-sira\Ui-autoplan-restore-20260806-025929.md -->
# Jack & Jill public architecture dossier and SIRA/SEIL build gap

- **Status:** Reviewed plan — sequential CEO, design, engineering, and DX review complete
- **Observed:** 6 August 2026
- **Scope:** Publicly accessible pages, documentation, code, company records, and unauthenticated product entry only
- **Companion plan:** `docs/plans/SEIL_AGENT_PARITY_AND_WEB_INGESTION.md`

## Executive verdict

Jack & Jill is not mainly a clever chatbot. It is a two-sided, consented matching network with four compounding assets:

1. live first-party context from both sides;
2. a role-specific compiler that turns an employer brief into inspectable reasoning gates;
3. continuous search and feedback that improves the brief and the candidate state;
4. distribution and completion loops across web, email, WhatsApp, Slack, ATS, referrals, and direct introductions.

Its public technical primitives are conventional: Next.js, FastAPI, PostgreSQL, structured LLM calls, scheduled work, and integrations. Its real leverage is the data and outcome flywheel around those primitives.

SIRA/SEIL already has several pieces Jack & Jill does not publicly demonstrate: a deterministic evidence-aware decision graph, authority-separated effects, counterfactuals, tenant RLS, versioned seller evidence, Prava payment authority, and Temporal checkout. The next product is therefore **not a Jack & Jill clone**. It is a Commerce Match OS that connects the existing control plane to a living product market.

## Research boundary

### What this document can establish

- Public product pages and documented user flows.
- Public frontend concepts visible before authentication.
- Technologies named in official hiring material.
- Data practices, permissions, and automation described in official docs and policies.
- Matching mechanics disclosed in official technical writing.
- Public company filings, funding announcements, trademarks, and open repositories.

### What this document cannot establish

- Private source code, prompts, schemas, queues, cloud accounts, or production data.
- Exact model providers, embeddings, retrieval index, ranking weights, thresholds, or cost controls.
- Whether every marketing claim is independently accurate.
- Operational work performed by humans behind the visible agent experience.

All non-public architecture below is labelled **INFERENCE** or **UNKNOWN**. Publicly readable code without a licence is not treated as reusable code.

## Public surface map

The public sitemap exposed 528 marketing/documentation routes and a separate jobs sitemap exposed roughly 970 job-detail routes at observation time.

### Acquisition and trust

- `/`, `/jack`, `/jill`, `/pricing`, `/faq`, `/friends`, `/about-us`
- Career clarity, salary negotiation, salary benchmarking, mock interview, and segmented engineer landing pages
- Blog, comparisons, press, guides, security/legal pages, and bias reporting
- `/companies` plus hundreds of company pages
- Public job feed and hundreds of job pages

### Jill documentation

- Getting started
- Search and candidate discovery
- Hiring brief
- Introductions
- Pipeline management
- Working with Jill
- Team joining and permissions
- Slack and Ashby integrations
- Pricing and FAQs

### Authenticated information architecture described by the docs

```text
Company workspace
├── Inbox
├── Cross-role pipeline
├── Roles
│   └── One persistent Jill per role
│       ├── Chat
│       ├── Search
│       ├── Brief (private operational truth)
│       ├── Pitch (candidate-visible projection)
│       ├── Pipeline
│       └── Configuration
├── Team and permissions
└── Integrations

Candidate workspace
└── One persistent Jack per person
    ├── Conversation and career profile
    ├── Job matches and feedback
    ├── Jill-network opportunities
    ├── Mock interviews and career coaching
    ├── Salary intelligence and negotiation
    └── Visibility and data controls
```

The unauthenticated app entry confirms separate candidate and employer paths. Candidate login offers LinkedIn or email. Employer login offers Google, Microsoft, or work email.

Public client routes reveal a wider surface than the marketing pages alone:

- Jack: onboarding, LinkedIn verification, candidate pack, dashboard, inbox, matches, opportunities, archive/kanban, referrals, CV/experience/call-note/memory/search documents, coaching and interview sessions, sharing/communication/account settings.
- Jill: company onboarding, role creation and bulk import, role chat/brief/history/pitch/search/pipeline/configuration, Jack-network and public-profile search, inbound/referral/external candidates, introduction and transfer flows, organization pipeline, team/templates/integrations/settings, scheduling/invite/referral/profile-claim flows.
- Some client route constants can be deprecated, experimental, or internal; their presence does not prove general availability.

## Product loops

### Jack: candidate-side loop

1. Authenticate and provide CV/LinkedIn, experience, preferences, location, and compensation context.
2. Build or refresh a structured candidate profile from chat, voice, email, and WhatsApp.
3. Search a claimed 15 million jobs daily.
4. Present web-sourced roles and Jill-managed roles with fit rationale.
5. Learn from yes/no feedback and later conversations.
6. Ask for candidate consent before sharing contact details for a Jill-managed role.
7. Prepare the person through research, coaching, mock interviews, and negotiation support.

### Jill: employer-side loop

1. Create or import a role from rough notes, a job description, or a careers URL.
2. Research the company, team, role, stage, and context.
3. Compile a versioned private hiring brief, a separate candidate-facing pitch, and a role-specific evaluation pipeline.
4. Calibrate with employer questions and reference candidates.
5. Search continuously across Jack's first-party network and public profiles as a cold-start fallback.
6. Explain per-criterion fit, uncertainties, and things to verify.
7. Learn from shortlists, passes, notes, chat, and reference profiles.
8. Request a consented introduction through the candidate's Jack.
9. Track the result in a role pipeline and optionally sync it to Slack and Ashby.

### Distribution and revenue loop

```text
Free candidate utility
  -> fresher candidate context
  -> better employer matches
  -> more consented introductions
  -> successful-hire fee
  -> more candidate utility and acquisition

Public company/job pages + referrals + CC-to-agent email
  -> low-friction acquisition
  -> more network liquidity
```

## Publicly disclosed matching system

Jack & Jill's official technical essay describes a bespoke funnel per role.

Each gate has:

- selected candidate fields;
- an explicit prompt/rubric with evaluation tiers;
- a structured output space;
- a composite pass condition.

Execution is described as one independent LLM call per candidate per gate. Early gates make cheap, narrow cuts such as location, visa, and function. Later gates evaluate more contextual traits. The population shrinks before expensive gates. Protected characteristics are stripped, relevant context is minimized, reference candidates calibrate the funnel, and “dye tests” trace known candidates through each gate. Prompts are reportedly inspectable in the brief UI.

```text
Role conversation + company research + reference candidates
                         |
                         v
              versioned hiring brief
                         |
                         v
       high-recall candidate population  [UNKNOWN implementation]
                         |
                         v
     gate 1 -> gate 2 -> gate 3 -> ... -> shortlist
       |          |          |
       +----------+----------+
          criterion explanations
                         |
                         v
     shortlist/pass/notes/outcomes recalibrate next run
```

The unspecified component is important: the company does not publicly disclose how it retrieves the initial high-recall population, stores embeddings, aggregates scores, chooses thresholds, schedules millions of calls, or controls cost and latency.

## Public technical and operational evidence

| Area | Public fact | Confidence |
|---|---|---:|
| Web | Next.js and TypeScript named in an official engineering role | High |
| API | Python and FastAPI named in the same role | High |
| Database | PostgreSQL named in the same role | High |
| Hosting | Marketing/docs are served by Vercel; authenticated app/API DNS and response evidence point to an AWS ALB in eu-west-2, with nginx at the API edge | High for observed edge, unknown compute |
| Authentication | Public app bundles and signed-out headers identify Clerk on a custom domain | High |
| Candidate context | LinkedIn OAuth, CV, phone, chat, voice, WhatsApp, and email are described | High |
| Matching | Per-role reasoning gates with structured rubrics and outputs | High |
| Feedback | Chat, shortlist, pass, notes, and reference candidates refine search | High |
| Background work | Continuous search and daily role review | High |
| Integrations | Slack and one-way Ashby lifecycle sync are documented | High |
| Analytics | Privacy policy names PostHog and Google Analytics | High |
| Client observability | Public bundles initialize Datadog RUM; PostHog is proxied through a first-party edge hostname | High |
| Support/marketing | Public bundles expose Front support, GTM, Mux video, and Logo.dev assets | High |
| Fairness | Public third-party Warden dashboard and internal protected-field removal | High, with limitations |
| Search/queue/models | Exact providers and architecture | Unknown |
| Hosting/observability | Exact production infrastructure | Unknown |

### Likely runtime architecture — INFERENCE

```text
Next.js web + email/WhatsApp/Slack channels
                 |
                 v
        FastAPI application boundary
                 |
        +--------+---------+
        |                  |
  PostgreSQL truth   asynchronous job system [UNKNOWN]
        |                  |
        |        +---------+----------+
        |        |                    |
        |  research/import jobs  search/gate batches
        |                             |
        +------ feedback/events ------+
                 |
           inbox + notifications
```

This inference follows from continuous searches, daily reviews, bulk imports, retries, agent email identities, and integration syncs. It does not establish the specific queue or workflow technology.

The public generated client appears to cover roughly 1,076 REST calls across candidate packs, memories, documents, companies, roles, searches, matching, chat, inbox, pipeline, scheduling, introductions, integrations, referrals, placements, health, and a substantial internal operations surface. Public API/client evidence also shows create/start/status/load-more/cancel/retry/restore/version-history patterns. This supports an asynchronous application architecture, not a synchronous prompt wrapper. A Redis health route exists, but Redis's precise role remains unknown.

## Agent system

### Product agents

- Jack is persistent per candidate.
- Jill is persistent and isolated per role, with its own brief, search, pipeline, configuration, and email address.
- The two agents represent opposing interests. Contact data crosses only after mutual consent.
- Chat controls work, but durable structured artifacts remain the operational record.
- Public clients expose streamed messages, stop, heartbeat, recovery, context reload, tool-input questions, tool-result messages, and debug views.
- Organization- and role-level agent handbooks have resolved views and activity history.
- Public operations clients expose model aliases, model routes, path policies, and cost summaries; actual providers and models remain undisclosed.

### Internal agent fleet

The official public GitHub repository describes internal agents such as Juno, Joy, Jo, Jedi, and Jeeves. Its framework uses four files:

- `SOUL.md`: persona and communication constraints;
- `AGENTS.md`: tools, permissions, triggers, workflows, and escalation;
- `MEMORY.md`: explicit durable facts and lessons;
- `BOOTSTRAP.md`: first-run orientation.

This is good operating discipline, not evidence of a proprietary multi-agent runtime. Their runner, scheduling, sandbox, tool protocol, memory store, and orchestration remain private. The repository has no visible licence file, so its contents should inspire structure, not be copied.

## Data and database model — facts and inference

### Explicitly implied records

- Person, company, organization membership, team role
- Candidate profile and visibility state
- Conversation/transcript and source provenance
- Employer role and role permissions
- Versioned private brief and candidate-facing pitch
- Evaluation criteria, signals, anti-signals, and reference candidates
- Candidate search result and criterion scores
- Shortlist/pass/note feedback
- Introduction consent and contact-share state
- Pipeline stage and hire outcome
- Channel/integration configuration
- Referral attribution and fee state

### Likely but unverified records

- Retrieval documents/embeddings or an equivalent search index
- Gate execution batches, gate attempts, model versions, prompts, tokens, and cost
- Scheduled review jobs, message deliveries, and retries
- Entity-resolution aliases and public-profile enrichment snapshots
- Fairness evaluation sets and drift history

## IP and moat assessment

### Defensible assets

1. Longitudinal first-party candidate intent rather than only scraped profiles.
2. Bilateral feedback and consent outcomes across candidates and employers.
3. Marketplace liquidity: candidates attract employers and employers create better candidate utility.
4. Per-role brief and rubric compilation grounded in deep context.
5. Distribution through public SEO pages, referral economics, agent email, and existing work channels.
6. Operational datasets for calibration, fairness, response probability, and successful introductions.

### Standard or reproducible pieces

- Next.js, FastAPI, and PostgreSQL.
- LLM-as-judge structured outputs.
- Progressive filtering and context minimization.
- Markdown personas and explicit memory.
- Slack, email, ATS, and calendar integrations.
- Public-profile enrichment and scheduled jobs.

### Legal/IP footprint

- The legal entity is Tinker Tailor Talent Limited, incorporated in the UK in March 2025.
- It announced a $20M seed in October 2025.
- UK trademark applications cover JACK & JILL and JACK AND JILL across recruitment/software classes.
- No public patent assigned to the company was found in this research; that is not proof that none exists or is pending.
- The visible strategy is brand, copyrighted software/prompts, proprietary data, network effects, and execution speed.

## Current SIRA/SEIL architecture

### Strong foundation already implemented

| Capability | Evidence in repository | Status |
|---|---|---|
| Persistent missions | `AgentMission`, events, tasks, artifacts, checkpoints, capability grants, effects | Implemented foundation |
| Agent runtime | OpenAI Agents SDK adapter, typed `MissionTurnOutput`, bounded tool registries | Implemented foundation |
| Buyer tools | Catalog/evidence reads, decision views, counterfactuals, purchase proposals | Implemented foundation |
| Seller tools | Product/draft reads, evidence research, claim/fit/anti-fit proposals, review request | Implemented foundation |
| Decision engine | Recall/deduplication, evidence policies, gates, exact ranking, bounds, robustness, counterfactuals | Strong deterministic core |
| Seller truth lifecycle | Product, claim, draft/revisions, evidence, review, version, suspension, export | Strong schema foundation |
| Buyer/seller exchange | Requirement briefs, engagements, candidate feedback, consent-oriented domain rules | Partial implementation |
| Auth and tenancy | Firebase identity, guest isolation, organization-scoped persistence, transaction-scoped PostgreSQL RLS | Data isolation foundation; team membership/RBAC missing |
| Protected effects | Approval/payment state machines, idempotency records, outbox, effect records | Strong transaction foundation; generic agent-effect execution is scaffolded |
| Durable workflows | Temporal checkout/reversal worker | Purchase only |
| Payment | Prava hosted authority plus controlled merchant adapter | Implemented integration boundary |
| Product research | SEIL web search can compile a research-only evidence artifact | Prototype, not durable ingestion |
| UI | Shared landing/auth, SIRA/SEIL workspaces, inbox, decisions, seller products/evidence | Partial artifact workspace |

Repository evidence:

- Shared workspace and closed-by-default inspector: `apps/web/components/workspace/commerce-workspace.tsx`.
- Verified Firebase identity and transaction-scoped RLS: `services/api/sira_api/identity.py`, `python/persistence/database.py`.
- Mission state and repository: `python/persistence/models.py`, `python/persistence/mission_repository.py`.
- Tool runtime and allowlists: `python/agents/sira_agents/runtime.py`, `python/agents/sira_agents/commerce_tools.py`.
- Deterministic graph: `python/decision_engine/graph_v1.py`, `graph_v1_recall.py`, `bounds.py`.
- Product Evidence lifecycle: `services/api/sira_api/seller_service.py`.
- Sanitized requirement and mutual contact-consent logic: `services/api/sira_api/service.py`.
- Checkout-only Temporal worker: `services/worker/sira_worker/workflows.py`.

Critical implementation truth:

- `WorkflowService.discover()` is explicitly non-production fixture mode, and `WorkspaceService.catalog()` still reads the demo fixture bundle.
- Frontend code still contains static catalogues and seeded conversations.
- SEIL research uses model web search but has no controlled capture, immutable source snapshot, excerpt locator, recrawl, or contradiction ledger.
- Bounded workers are protocols only; no durable research/task consumer exists. Autonomous continuation is synchronous extra model turns.
- Agent grants/effects are modeled but not yet the universal mutation boundary; the client still maps proposal types into direct APIs.
- Mission events are idempotent, but agent turns have no distributed run lock, expected-version reservation, or cached replay result.
- Feedback and outcome records do not yet recalibrate future decisions.
- Firebase roles are inferred from workspace mode; organization membership, invitations, role assignment, and ownership adjudication are incomplete.
- Runtime tracing is disabled and health does not prove worker/model/tool readiness.

### Strategic comparison

SIRA/SEIL is ahead on deterministic decision safety and transaction authority. Jack & Jill is ahead on the living network, continuous acquisition, operational feedback, cross-channel execution, and product polish. Adding more LLM autonomy before closing those loops would increase theatre, not value.

## What is left to build

| Gap | Current reality | Required end state | Priority |
|---|---|---|---:|
| Canonical market graph | Tenant seller records and fixture catalogue | Category-scoped product/vendor/plan identities first; global aliases, deduplication, ownership, and tenant-private overlays after the wedge works | P0/P2 |
| Durable public ingestion | One-turn SEIL web search and compiled artifact | Budgeted research runs, hostile-content-safe capture, immutable snapshots, typed claims, refresh schedules, cancel/resume | P0 |
| Live published catalogue | SIRA still depends on fixture/in-memory catalogue paths | Database-backed published Product Evidence read model used by SIRA discovery | P0 |
| Demand compiler | Requirements and deterministic gates exist, but no live demand-to-pipeline compiler | Turn each Requirement Brief into versioned eligibility gates, preferences, evidence policy, and search strategy | P0 |
| Hybrid retrieval | No production product recall/index | Structured filters + lexical/semantic recall + entity graph + deterministic dedup before expensive reasoning | P1 |
| Evidence reasoning funnel | Deterministic evaluation exists; LLM rubric generation is not a governed runtime | Bounded per-candidate evaluators with schema, citations, model/prompt versions, thresholds, dye tests, and cost budgets | P1 |
| Feedback learning | Feedback tables exist without a closed recalibration loop | Keep/eliminate/note/approval/outcome events update the brief or calibration set through reviewable versions | P1 |
| Model gateway | Direct per-run model/provider configuration | Aliases, route policy, fallback, cost/quality budgets, and traceable model selection | P1 |
| Stream/recovery protocol | Request/response chat plus persisted events | Streaming, stop, heartbeat, reconnect, replay-safe tool results, and mission recovery | P1 |
| Continuous work | Checkout Temporal worker only | Separate research, matching, re-evaluation, outreach, and notification workflows with inbox delivery | P1 |
| Two-sided exchange | Engagement records exist; full consented product introduction is incomplete | SIRA request -> SEIL response/pass -> mutual scoped contact consent -> negotiation/offer, preserving private boundaries | P1 |
| Product-scoped SEIL | Seller workspace exists, but the agent is mission/mode scoped | One durable SEIL identity per product/pack with its own memory, sources, inbox, tasks, and publication state | P1 |
| Object-scoped SIRA | Persistent conversations exist | One decision mission per buying object, with canonical brief, candidates, comparisons, approvals, and outcomes | P1 |
| Team tenancy | Firebase identity plus mode-derived roles | Organizations, membership, invitation, owner/editor/reviewer roles, verified assignment, and server-side capabilities | P0 |
| Agent effect runtime | Proposal tables and UI-dispatched handlers | Persisted turn/effect reservation plus bounded server registry, optimistic revision, expiry, and replay-safe completion | P0 |
| Proactive inbox | Basic inbox surfaces | New evidence, changed ranking, expiring offer, required authority, and workflow failures routed asynchronously | P1 |
| Connectors | Senso/Prava exist; business channels are sparse | Slack, email, calendar, CRM/procurement connectors with explicit scopes and replay-safe webhooks | P2 |
| Outcome flywheel | Outcome schemas exist | Verified adoption, renewal, savings, failure, and reversal outcomes recalibrate evidence and ranking without mutating history | P2 |
| Trust operations | Good boundaries, limited production eval/ops surface | Tool/model evals, source quality, drift, proxy-bias tests, cost/latency dashboards, deletion/retention, incident traces | P2 |
| Operations backoffice | No complete operator surface | Failed-run replay, integration repair, identity merge, dispute, billing, consent, and data-correction operations | P2 |
| Acquisition/network liquidity | Landing page only | Useful public product/category pages, vendor claim flow, buyer referrals, and embeddable/email entry paths | P3 |

## Target: Commerce Match OS

The target system keeps SIRA and SEIL asymmetric while sharing one governed market substrate.

```text
BUYER SIDE                                 SELLER SIDE
-----------                                -----------
Company graph + user conversation          Vendor sources + seller assertions
             |                                          |
             v                                          v
Versioned Requirement Brief                 Versioned Product Evidence
             |                                          |
             +----------------+  +----------------------+
                              v  v
                        MARKET TRUTH PLANE
              identities | claims | sources | versions
                     permissions | provenance
                              |
                              v
                    DEMAND PIPELINE COMPILER
          recall plan -> gates -> scoring -> evidence policy
                              |
                              v
                   HYBRID RETRIEVAL AND DEDUP
                              |
                              v
                  BOUNDED EVALUATION WORKFLOWS
             eligibility -> preference -> risk -> terms
                              |
                              v
          inspectable comparison + uncertainty + counterfactual
                              |
                  buyer action / ask vendor / consent
                              |
                              v
                offer -> approval -> Prava -> outcome
                              |
                              v
             immutable feedback and re-evaluation events
```

### Control-plane split

- **Models compile and explain:** intent, proposed criteria, search questions, evidence extraction, and bounded criterion judgments.
- **Deterministic code governs:** identity, provenance, eligibility, aggregation, permissions, ranking order, approval, money, and state transitions.
- **Temporal executes:** durable research, scheduled matching, re-evaluation, consent outreach, notifications, checkout, and recovery.
- **PostgreSQL records truth:** every version, event, source snapshot, judgment, effect, and outcome.
- **The UI exposes artifacts:** chat commands work; versioned Briefs, Product Evidence, matches, comparisons, and pipelines remain canonical.

## Delivery plan

### P0 — prove one buyer-first meeting-intelligence Decision Sprint

The first product works without seller accounts or marketplace liquidity. A buyer supplies a contract/invoice, existing product, or clear buying need and receives a governed renew/resize/configure/consolidate/cancel/replace or buy decision.

1. Add a category-scoped product identity and evidence registry for 20–30 meeting-intelligence products; retain an upgrade path to a global graph.
2. Add durable `research_run`, `source_snapshot`, `evidence_claim`, contradiction, policy, and refresh records.
3. Move research behind a dedicated Temporal queue with budgets, cancellation, checkpoints, and independent readiness.
4. Materialize reviewed Product Evidence into the database catalogue SIRA actually searches; remove fixture paths from live mode.
5. Compile the Requirement Brief into a versioned decision pipeline: hard gates, preferences, evidence rules, search plan, explicit unknowns, and company-stack effects.
6. Return three comparable candidates plus the no-buy/current-product action when supported; produce an approval-ready brief and exact next step.
7. Support one email-based structured vendor evidence/offer request. Seller participation improves the result but is never required for first value.
8. Replace mode-derived roles with verified organization membership and mutually exclusive owner/editor/reviewer capabilities.
9. Persist every agent turn and protected proposal/effect before execution; reserve mission version and idempotency key server-side.
10. Capture the immediate outcome: shortlist usefulness, approval-brief generation, vendor request/response, trial/evaluation/purchase start, and corrected claims.

### P1 — build the matching and calibration engine

1. Implement high-recall hybrid retrieval before reasoning gates.
2. Add bounded gate execution records: candidate, criterion, selected context, rubric, structured result, citations, model/prompt version, cost, and latency.
3. Run cheap deterministic gates first, then bounded LLM judgments only for materially ambiguous criteria.
4. Add calibration sets and dye tests using known positive, negative, and edge-case products.
5. Convert keep/eliminate/need-evidence/notes into proposed brief revisions, never invisible preference mutation.
6. Trigger idempotent re-evaluation when a brief or published Product Evidence version changes.
7. Explain what evidence or criterion changed the rank.
8. Add a small provider-neutral model-routing seam with logical aliases, task policies, fallback, cost, latency, and quality telemetry.

### P2 — complete the two-agent marketplace loop

1. Give each product a durable SEIL workspace/agent scope and each purchase decision a durable SIRA scope.
2. Complete selective Ask-vendor delivery with exact brief version, recipient, expiry, and withdrawal.
3. Support `PASS`, missing-field request, and structured offer as the only initial SEIL responses.
4. Add mutual, purpose-bound contact consent that remains separate from purchase authority.
5. Route asynchronous work to a cross-object inbox and selected external channels.
6. Ship email and Slack first; add HubSpot/procurement/calendar connectors only through scoped capability adapters.
7. Upgrade the agent transport with typed streaming, stop, heartbeat, reconnect, checkpoint restore, and replay-safe tool completion where long-running UX now requires it.

### P3 — outcome learning and trust operations

1. Capture verified implementation, adoption, renewal, savings, cancellation, reversal, and satisfaction checkpoints.
2. Use outcomes to update evidence reliability and calibration datasets through new immutable versions.
3. Add model/tool/source quality evaluations, bias/proxy tests, cost budgets, latency SLOs, and drift alerts.
4. Add end-user visibility, export, retention, deletion, and human-review controls for inferred data.
5. Publish a transparent methodology page only after the live controls and audit evidence exist.
6. Add a restricted operations console for failed runs, identity conflicts, connector repair, consent/disclosure disputes, and billing/data corrections.

### P4 — grow liquidity without weakening trust

1. Create useful public product and category pages from publishable evidence only.
2. Add vendor claim/invite flows and buyer/referral loops.
3. Support email-forward or CC-to-agent entry for buyers and sellers.
4. Expand categories after the meeting-intelligence vertical meets evidence, match, and outcome targets.

## UI and interaction contract

Use a **three-part workspace grammar**, not three permanently visible panes. Before an object exists, conversation may be primary. After a Brief or Product Evidence version exists, the structured artifact becomes primary. Chat and details appear only when invoked or when input/authority is required. Mobile shows one pane at a time.

### Canonical customer objects

```text
Organization / Workspace
├── Decision                         <- SIRA root object and canonical URL
│   ├── Decision Version
│   ├── Requirement Brief Version
│   ├── Candidate Evaluation Set
│   ├── Action Plan Version
│   ├── Authority Tasks
│   └── Outcome Checkpoints
├── Product                          <- SEIL root object and canonical URL
│   ├── Private Product Passport Version
│   ├── Evidence Draft Revision
│   ├── Published Product Evidence Version
│   └── Offer Version
└── Engagement
    ├── Requirement Brief Version
    ├── Product / recipient
    ├── Response / Offer
    └── scoped Consent Grants
```

Messages, agent runs, research runs, source snapshots, tool traces, compiler stages, and workflow queues are subordinate diagnostic records. Customer navigation uses Decisions, Products, and Inbox—not Missions or Agent Runs.

### Buyer activation storyboard

```text
Need, URL, invoice, or contract
  -> acknowledge within two seconds
  -> infer a draft Brief; ask zero questions when actionable, otherwise one material question
  -> create a durable Decision and safe-to-leave operation
  -> show sourced partial findings without exposing model reasoning
  -> notify through Inbox when the comparison is ready
  -> present incumbent/no-buy plus up to three comparable options
  -> show the best-supported action, decisive uncertainty, and one exact next step
  -> request authority only at the effect boundary
```

### Staged SEIL activation storyboard

```text
Paste product URL
  -> resolve identity and duplicates
  -> create a research-only Product Evidence packet
  -> show corrections, conflicts, unknowns, and freshness
  -> require verified seller authority before claim/private editing
  -> review and publish an immutable version
  -> later receive qualified requests without exposing buyer identity
```

### Chat-to-artifact transition

- Empty/new conversation: structured inspector closed.
- Greeting or ordinary chat: short response; no agent-run card and no inspector opening.
- Research running: compact inline status only; the user may leave safely.
- Material question: inline in conversation with why it matters and what it can change.
- First sourced partial: compact evidence summary; user chooses whether to inspect it.
- Decision ready on wide desktop: the structured Decision may become primary; agent diagnostics remain closed.
- Tablet/mobile: show **Review decision** and never steal the current pane or focus.
- Authority, failure, or changed result: explain inline; open the relevant artifact only after explicit user action.
- Once a versioned Brief or Product Evidence packet exists, collapse conversation by default when the user enters its structured view.

The first viewport of a completed Decision shows only:

1. best-supported action;
2. evidence or uncertainty that could change it;
3. one safe next action.

Raw scores, cost calculations, all sources, audit, and run traces are progressively disclosed. Recommendations show criterion-level evidence and uncertainty, never one opaque score.

### Human action rules

- Inline, reversible: keep, eliminate, need evidence, add note, correct requirement.
- Explicit review: proposed Brief revision with a visible before/after diff and the rank implications.
- Confirmed boundary: disclosure, vendor outreach, seller claim, publication, approval, consent, money, destructive changes.
- Never require a confirmation dialog merely because an LLM proposed a harmless UI preference.

### Asynchronous operation contract

Every background operation uses one of: `QUEUED`, `RUNNING`, `NEEDS_INPUT`, `PARTIAL`, `COMPLETED`, `FAILED_SAFE`, `CANCELED`.

Each state states what was preserved, whether leaving is safe, and where the user returns. Failure preserves the last verified artifact. Retry resumes the same operation/idempotency scope instead of creating another.

### Guest and identity boundary

- Allow isolated guest research and a private draft Decision.
- Preserve and migrate guest work when the anonymous Firebase identity links to Google/email.
- Require authenticated organization authority before outreach, organization data access, seller claim, publication, approval, or payment.
- Seller claiming always requires verified domain/company authority.

### Vocabulary and visual rules

- User-facing: Decision, requirements, product evidence, comparison, request vendor, approval, outcome.
- Internal only: mission runtime, compiler, gate execution, model route, market truth plane, workflow queue.
- Progress describes work and outcomes—“Checking your contract and product evidence”—never simulated thought.
- SIRA remains buyer language; SEIL remains seller language.
- Keep the light, border-led, dense B2B system and one design-token source. The user-selected blue/violet direction is a taste decision; if retained, update `DESIGN.md` and every shared token together rather than allowing code/doc drift.
- Do not copy Jack & Jill characters, wording, page structure, or trade dress.

### Accessibility and responsive acceptance

- One-pane operation at 320px with no page-level horizontal scroll.
- Composer and current authorized action stay reachable above the software keyboard.
- Comparison becomes a vertical option switcher; do not squeeze a desktop table.
- Sheets close before route navigation; focus returns to the invoking response/artifact.
- Automatic progress and artifact updates never move focus.
- Status uses a polite live region; the full chat is not live.
- All flows are keyboard operable; dialogs/sheets trap focus; reduced motion is respected.

### Experience milestones

- acknowledgment: under 2 seconds;
- durable operation visible: under 5 seconds;
- clear request: zero clarification questions;
- ambiguous request: at most one material question;
- first sourced partial: under 90 seconds when sources respond;
- complete shortlist/action: under 5 minutes after required sources are available;
- full Decision Sprint and optional authority step: within 10–15 minutes.

### P0 state/rescue matrix

| Stage | Loading/running | Partial or needs input | Failed/blocked | Stale/superseded | Success |
|---|---|---|---|---|---|
| Contract/source intake | Checking document and boundaries | show parsed facts + one material ambiguity | preserve upload; add URL/text | show newer source/version | draft Brief ready |
| Public research | compact safe-to-leave progress | show sourced findings + coverage gaps | resume same run or add proof | mark older snapshots | evidence set ready |
| Product recall | finding eligible products | show available candidates + recall gap | broaden approved scope | candidate version changed | evaluation set ready |
| Evaluation | evaluating material criteria | show completed gates + uncertainty | retry failed gates only | input version changed | Decision version ready |
| Vendor request | preparing exact sanitized brief | show preview + missing recipient/expiry | preserve unsent draft | underlying Brief changed | request delivered once |
| Proposal/approval | checking authority and exact payload | show missing approver/constraint | preserve proposal; no effect | require re-review of changed hash | approval/effect recorded |
| Outcome | waiting for verified checkpoint | show known result + unknowns | allow manual attestation | later evidence supersedes | immutable outcome checkpoint |

## Failure and rescue registry

| Failure | System behavior | User rescue |
|---|---|---|
| Ambiguous product identity | retain candidates; ingest nothing | choose the verified domain/product once |
| Blocked or hostile source | record failure; never convert snippet/instruction into fact | add an official URL or seller proof |
| Conflicting claims | preserve both snapshots and a contradiction group | show conflict; request authoritative proof |
| Stale price/security evidence | exclude from verified coverage by policy | refresh source or obtain seller attestation |
| Retrieval miss | record recall coverage and search strategy | broaden approved sources or invite vendor |
| Gate model failure | preserve earlier gates; retry within budget | show partial evaluation and safe retry |
| Feedback contradiction | propose a new brief version | user accepts, edits, or rejects recalibration |
| Duplicate/replayed event | reuse idempotent result | show existing artifact, never duplicate work |
| Seller does not respond | expire exact outreach safely | continue privately or choose another option |
| Consent expires/revokes | reveal no new identity and revoke future use | request consent again for a new scope |
| Worker unavailable | API remains readable and reports capability state | resume when the specific worker recovers |
| Model/provider outage | preserve mission and checkpoints | use deterministic results or retry later |
| Cross-tenant attempt | deny before record/tool access | generic denial with trace ID |
| Outcome unavailable | keep outcome unknown | never treat silence as success |

## Focused verification plan

- A clear buyer request produces a useful first candidate set without repetitive context questions.
- A clear product URL creates a sourced research-only packet with zero unsupported factual claims.
- Product identity resolution reuses canonical records and keeps merge lineage.
- Every displayed criterion result links to a rubric, evidence, model/prompt version, and execution record.
- Deterministic filters run before expensive judgments and produce the same result on replay.
- Calibration dye tests catch a deliberately misplaced positive, negative, and edge-case product.
- Keep/eliminate feedback proposes a brief revision; it never silently rewrites ranking preferences.
- Publishing new evidence creates one re-evaluation event and explains changed eligibility/rank.
- Background research and evaluation survive process restart, reload, cancellation, and retry.
- Anonymous and authenticated tenants cannot read or mutate each other's missions, sources, or drafts.
- Public research content cannot call tools, alter prompts, or access private addresses through redirects/DNS rebinding.
- Mutual contact consent reveals only approved fields and never grants purchase/payment authority.
- Slack/email retries do not duplicate messages or effects.
- Missing optional connectors degrade only their capability.
- A trace ID reconstructs the chain from message -> mission -> research -> evaluation -> effect without exposing secrets.
- Two concurrent chat turns cannot overwrite mission state, duplicate tools, or spend the same budget twice.
- A seller viewer cannot mutate evidence; an editor cannot approve their own publication; an anonymous session cannot claim a product.

## Success measures

- First sourced SEIL research packet in under 90 seconds for a known SaaS product.
- First useful SIRA candidate set with no question for a clear request and at most one material clarification otherwise.
- 100% of publishable claims satisfy evidence policy; unsupported claims shown as unknown.
- At least 80% of displayed research claims include a direct source and exact excerpt locator.
- Replayed requests cause zero duplicate research, publication, outreach, or payment effects.
- Zero cross-tenant leakage.
- Median gate cost and latency stay within declared per-mission budgets.
- Percentage of feedback events that produce accepted brief improvements.
- Percentage of new seller evidence that changes eligibility, uncertainty, or rank.
- Match-to-Ask-vendor, Ask-vendor-to-offer, and offer-to-approved-decision conversion.
- Verified post-purchase outcome coverage and rank-calibration improvement over time.

## Explicitly not in scope

- Copying Jack & Jill's branding, characters, recruitment vocabulary, layouts, prompts, or unlicensed repository text.
- Voice agents, career coaching, salary tools, job boards, ATS features, or recruitment-specific workflows.
- A general web crawler without category, source, cost, and retention boundaries.
- Seller-paid ranking.
- One monolithic autonomous agent with unrestricted browsing, messaging, or payment powers.
- Hidden preference learning that cannot be inspected or reverted.
- Claiming knowledge of Jack & Jill's private infrastructure or algorithms.

## Primary public sources

- [Jack](https://www.jackandjill.ai/jack)
- [Jill](https://www.jackandjill.ai/jill)
- [Jill documentation](https://www.jackandjill.ai/docs)
- [Getting started](https://www.jackandjill.ai/docs/getting-started)
- [Search and candidate discovery](https://www.jackandjill.ai/docs/search-and-candidate-discovery)
- [Hiring brief](https://www.jackandjill.ai/docs/hiring-brief)
- [Introductions](https://www.jackandjill.ai/docs/introductions)
- [Working with Jill](https://www.jackandjill.ai/docs/working-with-jill)
- [AI sourcing is broken by design](https://www.jackandjill.ai/blog/ai-sourcing-is-broken-by-design)
- [Privacy policy](https://www.jackandjill.ai/privacy)
- [Terms](https://www.jackandjill.ai/terms)
- [About and careers](https://www.jackandjill.ai/about-us)
- [Public agent guides](https://github.com/Jack-and-Jill-AI/Jack_and_Jill_AI_Guides)
- [Funding report](https://techcrunch.com/2025/10/16/jack-jill-raises-20-million-to-bring-conversational-ai-to-job-hunting/)
- [Warden assurance dashboard](https://trust.warden-ai.com/jackandjill/ai-candidate-matching)

## Autoplan Phase 1 — CEO review

### CEO verdict

**Proceed with a corrected premise.** The elite architecture remains coherent, but the initial plan made the destination look like the launch. SIRA must win a buyer decision without marketplace liquidity; SEIL and the two-sided network then compound demonstrated demand.

Initial strategy score: **6.3/10**. Revised sequence: **8.1/10**.

### Premise gate

Rejected premise:

> Build Jack & Jill for software procurement.

Accepted premise:

> Use the structural lesson—two loyal agents operating on durable, consented, evidence-backed state—to make one company-specific software decision materially better than generic search, then grow the network from actual demand and outcomes.

This changes sequencing, not the SIRA/SEIL idea.

### Existing leverage

- Deterministic decision graph with evidence policy, eligibility, ranking bounds, stability, and counterfactuals.
- Versioned buyer requirement and seller evidence domains.
- Mission/event/artifact persistence and tool-constrained agents.
- RLS, guest isolation, approval and payment state machines, idempotency/outbox, Prava, and checkout Temporal.
- A meeting-intelligence fixture and UI that already express the first vertical.

The scarce resource should therefore go into real market inputs and a closed outcome loop, not recreating generic agent infrastructure.

### Ten-star first experience

```text
Forward a contract/invoice OR state a meeting-intelligence need
  -> SIRA reads the company decision context
  -> returns renew / resize / configure / consolidate / cancel / replace / buy
  -> shows current product + three evidence-backed alternatives when relevant
  -> explains exact evidence, uncertainty, stack effects, and counterfactual
  -> prepares one vendor request or approval-ready action
  -> records the real result and uses it in the next decision
```

Target: useful governed value in 10–15 minutes, no seller account, no long setup, no visible multi-agent theatre.

### Alternatives considered

| Strategy | Advantage | Failure mode | Decision |
|---|---|---|---|
| Buyer-first Decision Sprint | Immediate standalone value; uses current engine; creates qualified demand | Can look like research unless it advances an action | **Chosen** |
| Seller-first Product Evidence passport | Builds supply and provenance | Vendors lack urgency without buyer demand | Defer |
| Full two-sided marketplace now | Closest to destination | Multiplies cold-start, trust, operations, and distribution risk | Reject for launch |

The chosen wedge is meeting-intelligence decisions, with renewal/deadline inputs preferred because urgency and value are measurable. New purchase evaluation remains supported when the user has no incumbent.

### Economics and distribution requirements

- The free/urgent buyer artifact is the approval-ready Decision Sprint, not a catalogue browse.
- Initial acquisition should exploit renewals, consultants/advisors, and forward-a-contract workflows rather than wait for public marketplace liquidity.
- A seller maintains evidence only when it reduces repetitive qualification or exposes visible qualified demand.
- Seller payment can never affect recall, qualification, evidence policy, or rank.
- A $12k annual tool cannot support high-touch enterprise procurement economics; the workflow must be low-cost, repeatable across renewals, or attached to larger spend at risk.

### Expansion gate

Do not expand beyond the meeting-intelligence vertical until all are true:

- 30 real Decision Sprints from at least 10 organizations;
- median time to a useful shortlist/action under five minutes after required sources are available;
- at least 70% of users mark the first result useful;
- at least 40% generate an approval brief or Ask-vendor request;
- at least 10 genuine vendor responses;
- at least five trials, evaluations, purchases, renewals, cancellations, or replacements begin;
- fewer than 10% of displayed factual claims require correction;
- evidence refresh cost and human exception work are sustainable.

### Temporal interrogation

| Horizon | Product state |
|---|---|
| First 30 days | Category evidence registry, live database catalogue, one durable research flow, one Decision Sprint |
| 60–90 days | Real buyer missions, email vendor request, approval brief, immediate outcome capture |
| After expansion gate | Governed matching/calibration, seller claim loop, automatic re-evaluation |
| After repeated demand | Product-scoped SEIL, mutual introductions, connectors, outcome learning, more categories |
| Destination | Commerce Match OS with bilateral network and transaction/outcome flywheel |

### Dual outside voices

#### CODEX SAYS (CEO — marketplace strategy)

The destination is strong, but the plan risks copying marketplace infrastructure before single-player demand exists. SIRA's durable company decision/outcome graph is more likely to be the initial moat than a generic product catalogue.

#### INDEPENDENT SUBAGENT (CEO — adversarial launch review)

The research is strong while the first plan is architecture-heavy. A narrow buyer-first vertical should prove that SIRA produces a better action than ChatGPT + review sites + email before building a generalized model gateway, connector portfolio, public market, or operations platform.

### CEO dual-voice consensus table

| Topic | Marketplace voice | Adversarial voice | Consensus |
|---|---|---|---|
| Core idea | Strong destination | Strong but overbuilt | Preserve Commerce Match OS |
| First user | Buyer with governed decision | Buyer with urgent category need | Buyer-first |
| First wedge | Renewal/action from contract context | Three-candidate decision + vendor request | Meeting-intelligence Decision Sprint |
| Marketplace timing | After buyer utility | Far later than initial draft | Not a launch dependency |
| Seller role | Demand-triggered evidence | Response normalizer first | Lightweight until qualified demand |
| Infrastructure | Narrow market/evidence substrate | Defer generic platform work | Build only what the closed loop uses |
| Success gate | Quantified action/value | Real missions and progression | Expansion metrics added |

### CEO failure-mode additions

- Generic research does not change a decision.
- The user gets a comparison but takes no next action.
- Sellers ignore structured evidence requests.
- Evidence operations cost more than the decision value.
- A category catalogue is mistaken for a network effect.
- Long company onboarding prevents first-session value.
- Broad category expansion destroys evidence freshness and comparability.

### CEO completion summary

| Review area | Result |
|---|---|
| Premise | Challenged and reframed; core idea preserved |
| Ten-star product | Defined as a buyer-first Decision Sprint |
| Alternatives | Three compared; buyer-first selected |
| Existing leverage | Explicitly mapped to current code |
| Scope | P0 narrowed; marketplace/platform work sequenced later |
| Economics/distribution | Requirements and seller incentive added |
| Temporal plan | 30/60/90-day and post-gate sequence added |
| Failure modes | Launch and network risks added |
| Success gate | Quantitative expansion gate added |
| Strategy score | 6.3/10 initial -> 8.1/10 revised |

> **Phase 1 complete.** CEO review is written into the plan. Phase 2 may now evaluate the UI/interaction plan against this buyer-first sequence.

## Autoplan Phase 2 — Design review

### Design verdict

The design system is disciplined, but the plan needed a precise first-session choreography. The decisive change is: **the Decision is the product object; chat is its command surface; missions and runs are diagnostics.**

Initial design completeness: **7.3/10**. Revised target: **9/10**.

### Seven-dimension scorecard

| Dimension | Initial | Revised target | Main correction |
|---|---:|---:|---|
| Information architecture | 7.5 | 9 | Decisions/Products become canonical; runs remain subordinate |
| Interaction model | 7 | 9 | Define chat-to-artifact transition and inspector-opening rules |
| Visual hierarchy | 7 | 9 | First viewport shows action, decisive uncertainty, one next step |
| States and rescue | 7.8 | 9 | Add asynchronous and stage-specific state/rescue contracts |
| Accessibility | 7.8 | 9 | Concrete focus, live-region, keyboard, and 320px acceptance |
| Responsive behavior | 7.8 | 9 | Three-part grammar; one pane at a time on mobile |
| Design-system fit | 7.5 | 9 | One token source; no mission/agent theatre or AI styling drift |

### Design decisions adopted

1. Customer-facing root objects are Decision, Product, and Engagement.
2. A new chat starts conversation-first; a durable artifact becomes primary after it exists.
3. Agent-run diagnostics never auto-open. An information control on the relevant response/artifact opens them.
4. A completed Decision may become primary on wide desktop; tablet/mobile requires explicit **Review decision**.
5. Clear requests ask zero clarification questions; ambiguous requests ask at most one material question.
6. Keep/eliminate/need-evidence stay inline; only consequential boundaries require confirmation.
7. Feedback produces a visible proposed Brief revision and rank-impact diff.
8. Background work is safe to leave, resumable, and returns through Inbox.
9. P0 recommendation UI is the semantic Option Matrix, not chat product-card shelves.
10. SEIL uses the same shell grammar but Product/Passport/Evidence/Offer language and asymmetric workflows.

### Explicit cuts

- Customer-facing Mission/New Mission/Missions language.
- Chat threads as the primary rail object once a Decision/Product exists.
- Empty third panes and permanent three-pane layouts.
- Separate decision room, payment app, or Agent Run workspace.
- Fixture work panels as production surfaces.
- Opaque fit scores without criterion evidence.
- Visible chain-of-thought, model plans, internal compilers, queues, or multi-agent choreography.
- Confirmation fatigue for reversible feedback.

### Dual outside voices

#### CODEX SAYS (Design — product-object review)

P0 still risked “chat plus panels.” Make the Decision canonical, define exactly when the artifact becomes primary, progressively disclose evidence, and remove mission/run vocabulary from customer navigation.

#### INDEPENDENT SUBAGENT (Design — first-time user review)

The architecture is strong but the “agent went to work and returned with value” moment was missing. Choreograph acknowledgment, durable operation, partial result, inbox return, completed comparison, and exact authority boundary without auto-opening UI.

### Design dual-voice consensus table

| Topic | Product-object voice | First-time-user voice | Consensus |
|---|---|---|---|
| Root object | Decision/Product | Artifact, not chat/run | Decision/Product canonical |
| Layout | Structured artifact primary after creation | Never three panes by default | Three-part grammar |
| Agent activity | Response info control | No visible reasoning theatre | Diagnostic only |
| First response | Short acknowledgment | Under two seconds | Milestone added |
| Clarification | Material only | Zero or one question | Hard limit added |
| Background work | Compact status | Safe-to-leave + Inbox | Async contract added |
| Authority | Exact server action | Confirmation only at consequence | Boundary table added |
| Mobile | Explicit artifact transition | One pane, focus-safe | 320px criteria added |

### Taste decision

The active branch is moving from the older green/copper accents to a user-selected blue/violet pair while `DESIGN.md` still names the old palette. This review does not reverse the user's direction. Before shipping, approve one pair and update `DESIGN.md`, global tokens, components, screenshots, and contrast evidence together. No parallel token systems.

### Design implementation checklist

- [ ] Rename customer-facing mission vocabulary to Decision/Product.
- [ ] Attach each conversation to one canonical Decision or Product.
- [ ] Implement inspector-opening and chat-collapse rules.
- [ ] Replace recommendation shelves with the semantic Option Matrix.
- [ ] Add async and P0 stage state/rescue matrices.
- [ ] Add proposed Brief before/after diff with rank implications.
- [ ] Preserve/migrate guest work and enforce authority boundaries.
- [ ] Verify keyboard, focus restore, live regions, reduced motion, and 320px layout.
- [ ] Consolidate color, typography, spacing, and state tokens.
- [ ] Keep SEIL asymmetric while reusing the shell grammar.

Mockups were not generated because the plan retains the existing production design language and resolves interaction architecture rather than proposing a new visual direction.

### Design completion summary

| Review area | Result |
|---|---|
| Scope | UI review required and completed |
| Seven dimensions | All scored |
| First-session journey | Buyer and staged seller storyboards added |
| Canonical IA | Decision/Product/Engagement defined |
| Async/rescue | State contracts and matrix added |
| Accessibility/responsive | Concrete acceptance criteria added |
| Design-system alignment | Existing system retained; token conflict flagged |
| Dual voices | Consensus recorded |
| Overall score | 7.3/10 initial -> 9/10 target |

> **Phase 2 complete.** Design outputs are written into the plan. Phase 3 may now lock architecture, data flow, rollout, and verification.

## Autoplan Phase 3 — Engineering review

### Engineering verdict

The existing decision/evidence/authority core should be extended, not replaced. Execution readiness was **6.6/10** because the live catalogue, global/private boundary, durable research, team authority, turn concurrency, and operational topology were unresolved. The locked design targets **8.6/10**.

### P0 runtime architecture

```text
Chat / contract / invoice
        |
        v
existing PurchaseRequest + versioned Requirement Brief
        |
        v
AgentTurn reservation <--- PostgreSQL lease + expected mission version
        |
        v
DecisionSprintWorkflow [Temporal queue: sira-decision]
        |
        +--> ProductResearchWorkflow [queue: sira-research]
        |      discover URL -> controlled fetch -> immutable snapshot
        |      -> untrusted claim draft -> deterministic evidence policy
        |
        +--> existing deterministic Decision Graph
        |      catalogue projection -> recall/dedup -> gates
        |      -> bounds/rank -> counterfactual
        |
        +--> immutable DecisionRecord + transactional outbox
        |
        v
Decision UI / Inbox / optional vendor-request effect

Separate queue: sira-checkout
Research/model failures cannot consume payment worker capacity or credentials.
```

PostgreSQL is canonical. Temporal stores orchestration history and stable IDs/hashes, not credentials, raw contracts/pages, prompts, private evidence, or chain-of-thought.

### Reuse boundary

Keep and extend:

- `PurchaseRequest`, `PurchaseBriefVersion`, `RequirementBriefVersion`.
- `EvaluationPipelineVersion`, `EvaluationRun`, discovery/candidate/gate/evidence/score/rank records.
- `DecisionRecord`, `CandidateFeedback`, `OutcomeCheckpoint`, `Engagement`.
- `AgentMission`, events, tasks, artifacts, checkpoints, grants, and effects.
- `IdempotencyRecord`, `OutboxEvent`, `WorkflowRun`.
- `SellerProduct`, drafts, evidence, review, and immutable `SellerPackVersion` as seller-owned truth.
- `graph_v1`, recall/deduplication, evidence policy, exact bounds, robustness, and counterfactuals.
- Existing decision-request APIs and Temporal composition/credential-free contracts.

Do not add in P0:

- a second decision engine;
- pgvector or a new search service for 20–30 products;
- a general crawler;
- a generic model-control product;
- a new event bus when the transactional outbox suffices.

### Data ownership boundary

```text
PLATFORM-SHARED, PUBLIC, READ-ONLY TO TENANTS
  catalogue identity + aliases
  immutable sanitized catalogue versions
  reviewed public claims + source excerpts/locators
  contradiction/freshness state

TENANT-PRIVATE, RLS-PROTECTED
  buyer documents, stack, Briefs, Decisions, feedback, outcomes
  research missions/runs and private source work
  seller Passport, assertions, drafts, evidence, offers
  membership, authority, consent, effects

ONE-WAY PROJECTIONS
  seller Pack version --sanitize/review--> public catalogue version
  research draft ------policy/review----> public catalogue version
```

Never move a tenant-owned `SellerProduct` into a global tenant. Public catalogue rows are immutable sanitized projections. Seller ownership is an explicit verified relation to a canonical product identity.

Tenant-owned foreign keys include organization identity in the key or use equivalent database constraints/triggers so a tenant row cannot reference a private row belonging to another organization.

### Schema additions

#### Shared publishable catalogue

- `catalog_products`: canonical product/vendor/domain/category, lifecycle state, current version pointer.
- `catalog_product_aliases`: normalized name/domain aliases and merge lineage.
- `catalog_product_versions`: immutable sanitized Product Evidence, authority class, content hash, source Pack reference when allowed.
- `catalog_evidence_claims`: typed predicate/value, policy result, freshness, contradiction state.
- `catalog_evidence_sources`: final URL, title, exact excerpt locator, excerpt/body hash, observed time, source class, verification method; no unrestricted raw HTML.
- `catalog_claim_sources`, `catalog_contradiction_groups`, and seller `product_ownership_claims`.

#### Tenant-private research

- `research_runs`: organization, mission/request/product, input hash, status, budgets, workflow IDs, checkpoint, cancel flag, attempts, output hash, safe error.
- `research_source_snapshots`: requested/final URL, fetch metadata, immutable bounded sanitized content/excerpt, hashes, source class, observed time, access/publishability state.
- `research_claim_drafts`: typed untrusted claim, exact source links, validation/policy state.
- `research_contradictions`: incompatible draft-claim groups.

Large retained source bodies, if needed, use encrypted S3-compatible object storage referenced by content hash. PostgreSQL holds canonical metadata and bounded excerpts. Retention/deletion policy is explicit.

#### Agent concurrency

- `agent_turns`: mission, client request/idempotency key, input hash, base mission version, status, lease owner/expiry, reserved budget, checkpoint/artifact, cached response, safe error, attempt.
- Add atomic mission event sequencing, preferably `AgentMission.next_event_sequence` updated with `UPDATE ... RETURNING`; `max(sequence)+1` is race-prone.

#### Organization authority

- `organization_memberships`: organization, actor, status, role/capabilities, verification method/time, inviter.
- `organization_invitations`: target, offered role, token hash, expiry, accepted/revoked state.
- Firebase proves identity only. Server-stored membership and verified claims grant capabilities.

Reuse existing evaluation, feedback, outcome, engagement, effect, and outbox tables rather than creating parallel models.

### Evidence authority pipeline

```text
URL discovery
  -> controlled fetch and immutable snapshot
  -> model extraction as UNTRUSTED CLAIM DRAFT
  -> deterministic source/freshness/contradiction policy
  -> optional seller/human attestation
  -> reviewer action when required
  -> immutable sanitized catalogue version
```

The model never assigns `VERIFIED`, publishability, authority, freshness, or seller ownership. A URL in model output is discovery metadata until the server fetches and hashes it.

### API contract

Preserve and evolve:

- `POST /v1/decision-requests`.
- `POST /v1/decision-requests/{id}/discover` returns `202` plus operation reference.
- `GET /v1/decision-requests/{id}` returns operation state, progress, `safe_to_leave`, last verified artifact, and required input.
- `GET /v1/decision-requests/{id}/decision-view`.
- Existing feedback/action routes.

Add only the P0 surface:

- `GET /v1/catalog/products?category=&q=`.
- `GET /v1/catalog/products/{id}?version=`.
- `POST /v1/research-runs/{id}/cancel`.
- `POST /v1/research-runs/{id}/resume`.
- `POST /v1/decisions/{id}/vendor-requests` bound to exact Brief version, recipient, expiry, disclosure projection, and idempotency key.
- Minimal membership/invitation endpoints that issue server-owned capabilities.

`/v1/workspace/catalog` delegates to the database catalogue during compatibility and is then deprecated; it does not become a second source of truth.

### Event contract

Transactional outbox events:

- `research.requested`, `research.partial`, `research.completed`, `research.failed_safe`;
- `source.snapshot.created`, `evidence.claim_draft.created`, `catalog.version.published`;
- `decision.evaluation.requested`, `decision.ready`, `decision.superseded`;
- `vendor_request.reserved`, `vendor_request.sent`, `vendor_response.received`, `vendor_request.expired`;
- `outcome.checkpoint.recorded`.

Every event includes event ID, organization/public scope, aggregate type/ID/version, causation/correlation IDs, idempotency key, occurred time, schema version, and a safe payload. Private contents remain referenced by ID.

### Temporal and worker contract

#### `DecisionSprintWorkflow`

1. Freeze exact Brief, stack, policy, and catalogue version set.
2. Reuse fresh catalogue evidence.
3. Start bounded child `ProductResearchWorkflow` instances only for missing/stale decision-material evidence.
4. Persist sourced partials and Inbox events.
5. Compile the existing `EvaluationPipelineVersion`.
6. Run the deterministic Decision Graph in an activity.
7. Atomically persist one Decision version plus outbox notification.
8. Finish as `COMPLETED`, `PARTIAL`, `NEEDS_INPUT`, `FAILED_SAFE`, or `CANCELED`.

#### `ProductResearchWorkflow`

1. Discover candidate URLs under a category/source policy.
2. Fetch through the controlled capture service.
3. Store immutable bounded snapshots.
4. Extract typed claim drafts in a model activity.
5. Apply deterministic evidence/freshness/contradiction policy.
6. Checkpoint after every source and stop on budget/cancel.
7. Never publish automatically.

Use Temporal for multi-step work with timers, external waits, cancellation, or compensation. Short extraction/indexing operations may remain bounded activities/outbox jobs. High-fanout work uses capped child workflows/activities and `continue-as-new`; never put an unbounded candidate corpus in one history.

A narrowly privileged dispatcher reads global outbox envelopes. Each activity then enters ordinary tenant-scoped transactions. Remove static `WORKER_ORGANIZATION_IDS` as the tenancy model for dynamic users. Research, decision, outreach, and checkout queues have separate credentials and scaling.

### Turn, workflow, and effect idempotency

- Reserve `agent_turns` before a model call; never hold a database lock during network/model work.
- Turn uniqueness: mission + client request key. Same key/same input returns the cached result; same key/different input returns `409`.
- A second active turn for one mission receives the existing operation instead of running concurrently.
- Finalization compares `base_mission_version`; stale output is not merged.
- Decision workflow ID: `decision-sprint:{org}:{request}:{brief_hash}:{catalog_set_hash}`.
- Research workflow ID: `product-research:{org}:{product}:{policy_hash}:{refresh_window}`.
- Every activity key includes run, stage, subject, and input hash.
- Catalogue current-pointer publication uses expected-previous-version compare-and-swap.
- Protected effects atomically reserve the effect and outbox message, dispatch with provider idempotency, reconcile unknown acknowledgements, then verify or compensate.
- Every state change and its outbox event commit together.

### Controlled capture security

- HTTPS only; approved ports; no URL credentials; maximum three redirects.
- Resolve DNS and re-check every redirect; reject private, loopback, link-local, metadata, reserved, and disallowed IPv4/IPv6 ranges.
- Strict connection/read timeout, MIME allowlist, compressed/decompressed size, document page, and parser limits.
- No browser cookies, authentication headers, user session, forms, JavaScript execution, or arbitrary downloads.
- Isolated parsing; fetched text is untrusted evidence input and never executable instructions.
- Strip query secrets from logs/storage and define robots/terms, malware, retention, deletion, and source-rights policy.
- A publishable claim requires final URL, exact locator, content hash, observed time, source class, and deterministic policy pass.
- Private buyer/seller records remain tenant-RLS protected; public projection code uses an explicit allowlist.

### Current defects to resolve in foundation

- Fixture-only discovery and in-memory catalogue in live paths.
- Artifact-only coercion can emit invalid mission state `EVALUATING`.
- A SEIL authentication error can name the SIRA credential.
- Mission event sequence calculation and synchronous turn lifecycle can race.
- UI proposal mapping bypasses a universal protected-effect handler.
- Workspace-mode-derived roles can grant seller mutation capability.
- Worker readiness and tenancy assume a fixed organization list.

### Migration, rollout, and rollback

1. Add tables, constraints, RLS policies, indexes, capabilities, and expected Alembic head—no destructive contract changes.
2. Load 20–30 reviewed products through a repeatable importer, never Alembic and never fictional fixture mutation.
3. Build one-way `SellerPackVersion -> catalog_product_version` sanitized projection.
4. Backfill fixture products as explicitly `PLATFORM_COMPILED` compatibility records.
5. Shadow database catalogue reads/evaluations beside fixture runs and diff frozen graph inputs/results.
6. Enable `turn_v2`, `market_v2`, `research_v2`, and `effects_v2` for one internal organization.
7. Replay retained Temporal histories with pinned/versioned workers before promotion.
8. Canary authenticated organizations, then guests; production fixture mode turns off only after parity evidence.
9. Contract/remove fixture-only paths after the rollback window.

Rollback disables flags and stops new workers while preserving immutable rows, events, and outbox state. Never roll back by destructively reversing schema. Existing users receive lazy owner membership for their personal workspace; guests remain isolated and cannot acquire organization authority.

### Performance and cost targets

- Create/accept Decision Sprint: p95 under 500 ms.
- Durable operation visible: under 5 seconds.
- Catalogue recall over 30 products: p95 under 150 ms.
- Deterministic evaluation after inputs freeze: p95 under 750 ms.
- First sourced partial: under 90 seconds.
- Complete shortlist/action: under 5 minutes after required sources respond.
- Zero duplicate effects or Decision versions under replay/concurrency.
- Explicit per-run source/model/token/time budgets; exhausted budget returns an honest partial.
- Cache a material criterion judgment only by product-evidence version + rubric hash + relevant context hash + model route/version.
- Deterministic gates and top-N caps precede model judgments.
- Research load never degrades checkout capacity.

### Engineering complexity registry

| Risk | Control |
|---|---|
| Dual seller/catalogue truth | one-way immutable sanitized projection only |
| Temporal/PostgreSQL split brain | persist workflow ID before dispatch; reconcile orphaned/stale runs |
| Model nondeterminism | drafts only; deterministic authority policy; version every judgment input |
| Global/private leakage | separate models and explicit public projection allowlist |
| Identity merge corruption | immutable aliases/merge lineage and reversible adjudication |
| Evaluation cost explosion | small P0 corpus, deterministic first, top-N, budgets, cache |
| Workflow history growth | bounded children, payload references, `continue-as-new` |
| Provider unknown outcome | effect reconciliation and provider idempotency |
| Version skew | expand/backfill/shadow/cutover plus worker replay |
| Scope explosion | no pgvector, general crawler, broad connectors, or new decision engine in P0 |

### Focused engineering test matrix

| Layer | Required proof |
|---|---|
| Unit | Catalogue versions compile into current graph candidate/evidence contracts |
| Unit | Demand compiler emits replayable pipeline versions and preserves unknowns |
| Unit | Turn reservation handles replay, key/hash conflict, lease expiry, stale mission version |
| Unit/security | Fetch policy rejects private redirects, DNS rebinding, oversize/decompression, MIME spoofing, hostile content |
| Property | Input ordering/duplicates cannot change deterministic ranking |
| Postgres concurrency | Simultaneous turns cannot lose state, duplicate sequence, or spend twice |
| Postgres/RLS | Global public read works; private research/drafts/memberships cannot cross tenants |
| Publication | Catalogue versions immutable; current pointer and seller projection are CAS-safe |
| Temporal | Retry, restart, cancel, partial, resume, budget exhaustion, worker loss, version replay |
| Contract/security | Workflow payloads contain no credentials, raw documents/pages, prompts, or private source text |
| API | `202 -> partial -> completed`, cancel/resume, evidence links, safe failures, cached replay |
| Effect | Crash before/after dispatch, provider unknown result, webhook replay, verify/compensate |
| Migration | Old/new API-worker version skew, shadow parity, flag rollback, backup/restore |
| End to end | Clear meeting-intelligence request returns incumbent/no-buy plus up to three sourced options and one action |

### Dual outside voices

#### CODEX SAYS (Engineering — architecture lock)

Build a durable Decision Sprint around the current decision engine. Add the shared catalogue projection, tenant-private research, turn reservation, membership authority, two bounded Temporal workflows, and minimal APIs. Avoid a second engine or premature search platform.

#### INDEPENDENT SUBAGENT (Engineering — adversarial reliability)

P0 still failed if global vs tenant truth, model evidence authority, controlled capture, concurrent turns, dynamic worker tenancy, and effect dispatch remained implicit. These are foundation correctness, not optional hardening.

### Engineering dual-voice consensus table

| Topic | Architecture voice | Reliability voice | Consensus |
|---|---|---|---|
| Decision core | Reuse `graph_v1` | Do not add smarter matching first | Reuse and feed real data |
| Catalogue | Shared sanitized projection | Global/private boundary mandatory | Separate shared/public from tenant/private |
| Research | Two bounded workflows | Controlled fetch before ingestion | Durable, policy-governed capture |
| Agent turns | Reserve + CAS | Current flow can duplicate work | Persisted lease/idempotency required |
| Effects | Reuse effect/outbox | UI direct calls are unsafe | Universal bounded effect runtime |
| Temporal | Decision/research queues | Not a universal queue | Use for long-running coordination only |
| Auth | Membership rows | Mode-derived role is unsafe | Server-owned capabilities |
| Rollout | Shadow/canary | Never destructive rollback | Expand/backfill/shadow/cutover |
| Search | PostgreSQL sufficient in P0 | Bound fanout/cost | Hybrid/vector stays P1 |

### Engineering completion summary

| Review area | Result |
|---|---|
| Architecture/data flow | Locked with diagram |
| Reuse vs new code | Explicit |
| Data ownership | Global/public vs tenant/private defined |
| Schema | Additions and reuse boundary defined |
| APIs/events | Minimal contracts defined |
| Workflows | Decision and research workflows plus queue isolation defined |
| Idempotency/concurrency | Turn/workflow/activity/effect rules defined |
| Security | Controlled capture and authority boundaries defined |
| Rollout/rollback | Additive, shadowed, canaried, flag-reversible |
| Performance/cost | Measurable targets and budgets defined |
| Verification | Focused matrix defined |
| Dual voices | Consensus recorded |
| Score | 6.6/10 initial -> 8.6/10 revised |

> **Phase 3 complete.** Engineering outputs are written into the plan. Phase 3.5 may now review developer and operator experience.

## Autoplan Phase 3.5 — Developer and operator experience

### DX verdict

The architecture is safer than its operating experience. A developer can run the fixture stack, but cannot currently prove that the database catalogue, Temporal, research/decision workers, model, and source capture are live. Current DX: **5.0/10**. Target after the following work: **8.9/10**.

### Primary persona and journey

Primary persona: a full-stack product engineer on Windows who develops locally and operates Vercel + Railway. They need one reliable path from fresh clone to a visible Decision Sprint and one command that explains every blocker.

| Stage | Current experience | Required P0 experience |
|---|---|---|
| Discover | README explains the product and fixture demo | README links to P0 quickstart, topology, modes, and live-vs-fixture contract |
| Configure | One large `.env.example`; dependencies are implicit | Doctor validates non-secret requirements and capability-specific secrets by mode |
| Start | DB/API and web are separate; local Temporal absent; checkout worker optional | One command starts DB, migration, Temporal, object store, API, decision/research workers, and web |
| First success | Fixture UI does not prove P0 runtime | One canonical request proves `202 -> PARTIAL -> COMPLETED` |
| Debug | API diagnostics exist; worker retries/readiness are opaque | One trace ID, structured safe logs, capability readiness, heartbeat, queue/outbox lag, exact recovery |
| Test | Broad suite is strong | One fast P0 smoke plus restart/cancel/resume/idempotency proof |
| Deploy | Docker image exists; dashboards hold operational knowledge | Version-controlled Railway/Vercel service/env matrix and release procedure |
| Roll back | Strategy exists in prose | Flags, worker drain, image rollback, compatibility window, restore drill |

### Eight-dimension scorecard

| Dimension | Current | Target | Correction |
|---|---:|---:|---|
| Getting started/discovery | 5 | 9 | one P0 quickstart and declared modes |
| Environment/setup | 5 | 9 | preflight, local Temporal/storage, one start command |
| First success | 3 | 9 | canonical real Decision Sprint smoke |
| API/SDK clarity | 7 | 9 | typed errors, capability discovery, one contract sync |
| Errors/debugging | 5.5 | 9 | correlated worker/provider diagnostics and safe next action |
| Observability/measurement | 2.5 | 9 | readiness, heartbeat, lag, cost/latency, TTHW and failed-safe metrics |
| Testability | 7 | 9 | focused lifecycle/replay harness |
| Deploy/upgrade/rollback | 4 | 8.5 | executable release matrix, canary, replay, rollback and restore |

### Explicit runtime modes

- `fixture`: deterministic UI/domain development; visible label; no provider claims.
- `sandbox`: real PostgreSQL, Temporal, controlled source capture, model adapter, and sandbox connectors.
- `production`: fixtures and demo identity disabled; required capabilities validated; no fallback.

The web data mode and API mode must agree. Production build/start fails if fixture mode is enabled. Preview can use fixtures only when visibly labelled and explicitly configured.

### One-command local entry

`./scripts/dev.ps1 -Mode sandbox` must:

1. validate Node/Python/Docker/Corepack versions, ports, and non-secret configuration;
2. start PostgreSQL, local Temporal + UI, and local S3-compatible storage;
3. run the one-writer migration;
4. start API, decision worker, research worker, and web;
5. start outreach/checkout only when their mode/capabilities are requested;
6. wait for readiness and print URLs, mode, build SHA, catalogue source, and one next command.

Provide a Bash wrapper backed by the same implementation for CI/Linux rather than maintain two independent validators.

### Capability doctor and readiness

`./scripts/doctor.ps1 -Mode sandbox` reports `disabled`, `misconfigured`, `starting`, `ready`, `degraded`, or `offline` for:

- database, runtime role/RLS, and migration head;
- API and web/API origin agreement;
- Firebase project coherence and guest/account-link readiness;
- Temporal namespace and decision/research/outreach/checkout queues;
- last worker heartbeat and outbox/queue lag;
- catalogue source/version and controlled fetch/object storage;
- model route, Senso, Prava, and controlled merchant.

Each blocker has a stable safe code, retryability, and one exact remediation. It never prints secret values.

Health contract:

- `/health/live`: process is alive.
- `/health/ready`: API database, migration, runtime-role/RLS readiness.
- `/v1/capabilities`: authenticated mode/capability roster, worker heartbeat age, safe blocker, remediation, build/API/catalogue versions.

A green API never implies that a Decision Sprint or payment is runnable.

### Canonical P0 quickstart and smoke

Document and automate:

```text
create meeting-intelligence request
  -> discover returns 202 + operation ID
  -> status becomes RUNNING/PARTIAL
  -> sourced partial appears
  -> final Decision includes incumbent/no-buy + up to three options
  -> identical replay returns cached result
  -> cancel/resume preserves the same run
```

`./scripts/smoke-p0.ps1` checks only migration head, request acceptance, worker pickup, sourced partial, completed Decision, replay, cancel/resume, and duplicate-effect absence. It does not run the full lint/type/test suite.

### API/client and error contract

One `contract:sync` command generates/checks OpenAPI and the TypeScript client under explicit deterministic settings.

Generated client errors preserve:

- `code`;
- `message`;
- `request_id` / trace ID;
- `retryable` and `retry_after`;
- `next_action`;
- bounded `details`.

HTTP status/text is fallback only. Worker logs use correlation ID, aggregate/version, workflow/run/activity, stage, attempt, safe error code, and budget—not prompts, credentials, or private content.

### Observability and restricted trace workflow

Expose or record:

- worker heartbeat and queue/outbox age/failures;
- workflow/run stage, retry, cancel, resume, and failed-safe counts;
- source discovery/fetch/policy outcomes and evidence coverage;
- model/source latency, token/cost budget, and cache hit;
- Decision completion, partial, correction, and duplicate-prevention metrics;
- canary/shadow parity and rollback recovery;
- TTHW from command start to ready and request to durable/partial/completed milestones.

A restricted trace command/view accepts one trace ID and reconstructs request -> AgentTurn -> workflow/activity -> research/evaluation -> effect/provider without revealing secrets or raw private evidence.

### Deployment topology and runbook

Version-control a Railway/Vercel matrix for:

- one-writer migration release job;
- API service;
- decision worker;
- research worker;
- outreach worker when enabled;
- checkout worker;
- PostgreSQL, Temporal, and object storage;
- Vercel build/runtime values, preview/production origins, Firebase public config, callbacks.

Each service documents command, queue, credentials, required/optional env, readiness, scaling/restart policy, owner, and rollback image. Research never requires Prava/merchant credentials.

Release runbook includes deployment order, migration compatibility window, feature-flag owner/default/expiry, shadow threshold, Temporal worker replay/versioning, one-organization canary, worker drain, previous-image rollback, and backup/restore verification.

### Documentation set

- `docs/getting-started.md`
- `docs/configuration.md`
- `docs/api/decision-sprint.md`
- `docs/operators/readiness.md`
- `docs/operators/runbook.md`
- `docs/deploy/railway-vercel.md`
- `CHANGELOG.md`

The environment matrix groups variables by fixture/sandbox/preview/production and by web/API/migration/decision/research/outreach/checkout ownership. `.env.example` remains the index, not the only explanation.

### Expected support-ticket risks

| Ticket | Preventive signal |
|---|---|
| Fixture products appear instead of live agent data | visible mode/catalogue source + production fail-closed |
| API health green but research never finishes | independent worker/queue readiness and lag |
| Vercel calls localhost/stale Railway URL | build/start origin coherence check |
| Firebase login works but API returns 401 | Firebase project/audience diagnostic |
| Worker blocked by unrelated payment credentials | split worker entrypoints/env |
| New organization never processed | dynamic dispatcher; remove static org allowlist |
| Migration permission denied | one-writer release job and admin/runtime URL check |
| OpenAPI/client drift | single contract-sync command in CI |
| Provider deployed but unavailable | capability manifest and safe blocker code |
| Additive migration needs rollback | flag disable + worker drain + previous image; no destructive down migration |

### Time to first success

- Current labelled fixture: approximately 15–30 minutes cold.
- Current real Decision Sprint: unbounded/blocked by incomplete topology and preflight.
- Target warm local sandbox: under 5 minutes.
- Target cold clone with dependencies present: under 10 minutes.
- Target credentialed hosted proof after secrets supplied: under 15 minutes.
- Durable operation visible after request: under 5 seconds.

### Dual outside voices

#### CODEX SAYS (DX — developer journey)

The repository has strong contracts and checks but lacks one complete runtime entrypoint. Make the real P0 journey the quickstart, split workers, add a capability doctor, typed errors, correlated operations, and a focused smoke command.

#### INDEPENDENT SUBAGENT (DX — operator adversity)

The plan names queues, flags, canaries, and rollback while the repo still has one checkout worker, DB-only health, no local Temporal profile, and no release runbook. “Operator can prove what is running” must itself be a P0 capability.

### DX dual-voice consensus table

| Topic | Developer voice | Operator voice | Consensus |
|---|---|---|---|
| Modes | explicit fixture/sandbox/production | prevent fixture/live confusion | no implicit fallback |
| Startup | one full-stack command | preflight every dependency | doctor + dev command |
| Workers | split by capability | separate credentials/readiness | decision/research/outreach/checkout |
| Health | readiness by subsystem | API green is insufficient | live/ready/capabilities |
| First success | canonical 202/partial/completed | observable worker pickup | focused P0 smoke |
| Errors | typed API problem | correlated worker/provider trace | stable code + one next action |
| Contracts | generated client retained | eliminate drift | one contract-sync command |
| Deploy | documented service matrix | executable canary/rollback | version-controlled runbook |
| Measurement | TTHW and P0 flow | queue/failed-safe/rollback metrics | P0 DX telemetry |

### DX implementation checklist

- [ ] One command starts the complete P0 sandbox stack.
- [ ] Doctor identifies every blocker without exposing values.
- [ ] Fixture/sandbox/production never silently mix.
- [ ] Decision, research, outreach, and checkout workers have independent queues/readiness/secrets.
- [ ] Research starts without payment credentials.
- [ ] Canonical `202 -> PARTIAL -> COMPLETED` example and smoke work.
- [ ] Generated client preserves structured problems and syncs with one command.
- [ ] One trace ID reconstructs an operation safely.
- [ ] Warm TTHW is under five minutes.
- [ ] Migration has exactly one writer.
- [ ] Canary and rollback are executable and measured.
- [ ] Service/environment ownership is version-controlled.

### DX completion summary

| Review area | Result |
|---|---|
| Product/persona | Internal platform + long-running worker system; full-stack operator |
| Journey | Discovery through rollback mapped |
| Eight dimensions | All scored |
| TTHW | Current and target defined |
| Setup/readiness | Modes, doctor, one-command entry and health defined |
| API/errors | Contract sync and typed problem details defined |
| Observability | Trace, heartbeats, lag, cost and P0 metrics defined |
| Deploy/rollback | Service/env matrix and executable runbook defined |
| Support risks | Ten likely tickets and prevention mapped |
| Dual voices | Consensus recorded |
| Overall score | 5.0/10 current -> 8.9/10 target |

> **Phase 3.5 complete.** DX overall: 5.0/10 current -> 8.9/10 target. TTHW: unbounded for real P0 -> under five minutes warm.

<!-- AUTONOMOUS DECISION LOG -->
## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---:|---|---|---|---|---|---|
| 1 | CEO | Treat Jack & Jill as structural reference, not a clone target | Mechanical | P5 Explicit | Public evidence cannot establish private implementation; product risks differ | Copy pages/agents literally |
| 2 | CEO | Keep Commerce Match OS as destination | Taste | P1 Completeness | Preserves coherent two-agent/evidence/authority vision | Reduce product permanently to research assistant |
| 3 | CEO | Launch buyer-first before marketplace liquidity | Taste | P3 Pragmatic | Produces standalone value and tests demand with current leverage | Require seller network in P0 |
| 4 | CEO | Use meeting-intelligence Decision Sprint; prefer renewal/deadline inputs while supporting new purchase | Taste | P3 Pragmatic | Unifies urgency and the existing vertical without changing the core idea | Renewal-only or generic all-category launch |
| 5 | CEO | Gate expansion on real missions/actions/vendor responses | Mechanical | P6 Action | Prevents architecture work from substituting for product evidence | Expand by roadmap date alone |
| 6 | Design | Make Decision/Product canonical; keep chat as command surface | Mechanical | P5 Explicit | Durable artifacts are inspectable and recoverable | Chat thread/mission as root object |
| 7 | Design | Use three-part grammar, not permanent three-pane layout | Taste | P5 Explicit | Matches prior user direction and improves focus/responsive use | Always-open rail/chat/details |
| 8 | Design | Never auto-open Agent Run diagnostics | Mechanical | P5 Explicit | Useful work proves agency; diagnostics are optional | Visible agent theatre |
| 9 | Design | Allow isolated guest research; require auth/authority for effects | Taste | P1 Completeness | Fast activation without weakening disclosure/publication/payment boundaries | No guest or unrestricted guest |
| 10 | Design | Preserve user-selected blue/violet direction pending one-source token update | Taste | P6 Action | Avoids silently reversing a user choice while flagging doc/code drift | Revert to old palette now |
| 11 | Engineering | Reuse existing decision graph/evidence/effect domains | Mechanical | P4 DRY | They already encode stronger deterministic controls | Build a second engine |
| 12 | Engineering | Separate shared public catalogue from tenant-private research/seller truth | Mechanical | P5 Explicit | Prevents global/private leakage and misuse of tenant SellerProduct rows | Shared magic tenant |
| 13 | Engineering | Category-scoped PostgreSQL recall in P0; defer vector/hybrid platform | Taste | P3 Pragmatic | 20–30 products do not justify new search infrastructure | pgvector/search service now |
| 14 | Engineering | Model output remains untrusted until controlled fetch/policy/review | Mechanical | P1 Completeness | URL text cannot establish authority or publishability | Model-declared verified claims |
| 15 | Engineering | Reserve agent turns and effects before external work | Mechanical | P5 Explicit | Prevents duplicate spend, lost state, and duplicate side effects | Process-local concurrency only |
| 16 | Engineering | Use Temporal only for durable multi-step coordination; split queues | Taste | P3 Pragmatic | Preserves recovery without turning Temporal into a universal queue | One worker/queue or all jobs as workflows |
| 17 | Engineering | Expand/backfill/shadow/canary/cutover; rollback with flags/images | Mechanical | P1 Completeness | Immutable schemas/workflows require compatibility, not destructive reversal | Big-bang migration/down migration |
| 18 | DX | Declare fixture/sandbox/production with no fallback | Mechanical | P5 Explicit | Removes the highest-probability demo/live confusion | Ambient env inference |
| 19 | DX | Add doctor, one-command dev stack, and focused P0 smoke | Mechanical | P6 Action | Turns the plan into a provable operating path | README fragments and full suite only |
| 20 | DX | Split decision/research/outreach/checkout workers and secrets | Mechanical | P2 Boil lakes | Direct blast radius of queue isolation and optional capabilities | Shared checkout-dependent worker |
| 21 | DX | Extend existing capability endpoint and generated client | Mechanical | P4 DRY | Reuses present contracts rather than create parallel diagnostics | New unrelated admin API/hand client |

### User challenges and taste decisions

No user challenge changes the stated SIRA/SEIL idea. The review explicitly preserves the elite two-agent Commerce Match OS architecture. It narrows **launch sequencing**, because the user asked what remains to build, not for a literal Jack & Jill clone.

Taste decisions surfaced:

- Renewal-led vs new-purchase wedge: one Decision Sprint supports both; renewal/deadline inputs are preferred for measurable urgency.
- Wide-desktop artifact transition: a completed Decision may become primary when it is the useful result; Agent Run diagnostics never auto-open. Tablet/mobile requires explicit review.
- Brand palette: retain the user's blue/violet direction for now, but shipping requires `DESIGN.md` and all tokens/contrast evidence to agree.
- Semantic/vector retrieval: deferred until the category corpus and measured recall justify it.

## GSTACK REVIEW REPORT

### Review scope

- **Plan:** `docs/plans/JACK_AND_JILL_ARCHITECTURE_GAP_PLAN.md`
- **Restore point:** `C:\Users\sandi\.gstack\projects\siel-n-sira\Ui-autoplan-restore-20260806-025929.md`
- **Focused test artifact:** `C:\Users\sandi\.gstack\projects\siel-n-sira\Ui-autoplan-test-plan-20260806.md`
- **UI scope:** yes
- **DX scope:** yes
- **Outside voices:** two independent subagents per phase; a distinct Claude runtime was unavailable, so no output is represented as Claude.

### Final crux

Jack & Jill's public advantage is a living two-sided data, feedback, consent, and distribution loop—not a secret model architecture. SIRA/SEIL already has the harder deterministic decision/authority foundation. What remains is to connect that foundation to trustworthy live market evidence and one real buyer outcome.

### Locked build order

1. **Trust foundation:** membership/capabilities, turn reservation, universal protected effects, global/public vs tenant/private constraints.
2. **Live evidence:** controlled capture, immutable snapshots/claim drafts, category catalogue, research worker.
3. **Decision Sprint:** database catalogue -> existing graph -> incumbent/no-buy + up to three options -> approval-ready action.
4. **Demand-triggered exchange:** one email vendor request, normalized response, seller claim/review, re-evaluation.
5. **Calibration:** visible Brief revisions, dye tests, outcome checkpoints, cost/quality/trace operations.
6. **Marketplace expansion:** product-scoped SEIL, mutual consent, channels/connectors, additional categories only after the expansion gate.

### Phase scores

| Phase | Initial | Reviewed target | Central improvement |
|---|---:|---:|---|
| CEO | 6.3 | 8.1 | buyer-first wedge and expansion gate |
| Design | 7.3 | 9.0 | Decision/Product canonical; explicit agentic journey |
| Engineering | 6.6 | 8.6 | trust/data/concurrency/workflow boundaries locked |
| DX | 5.0 | 8.9 | one provable runtime path, readiness, canary/rollback |

### Dual-voice results

| Phase | Consensus |
|---|---|
| CEO | 7/7 themes aligned; preserve destination, narrow launch |
| Design | 8/8 themes aligned; artifact-first without agent theatre |
| Engineering | 9/9 themes aligned; real data into existing engine, fail closed |
| DX | 9/9 themes aligned; prove what is running and how to recover |

### Required artifact verification

- [x] Fact/inference/unknown public architecture dossier.
- [x] Public page and product-flow map.
- [x] Current-repository evidence and gap matrix.
- [x] Premise challenge, alternatives, ten-star state, temporal sequence, economics, and expansion gate.
- [x] Error/rescue and failure-mode registries.
- [x] Explicit not-in-scope list.
- [x] Seven-dimension design scorecard, state matrix, responsive/accessibility criteria.
- [x] Architecture/data-flow diagrams, schema/API/event/workflow contracts.
- [x] Security, concurrency, cost/performance, migration, rollout, and rollback design.
- [x] Focused test plan on disk.
- [x] Eight-dimension DX scorecard, TTHW, readiness, support risks, and runbook contract.
- [x] Incremental decision audit trail.

### Remaining implementation risk

The plan is executable, but the product is not yet proven. The decisive unknown is whether a real buyer takes a materially better action than they would with general-purpose AI, review sites, and email. That is why the expansion gate measures decisions and vendor responses—not feature completion.

### Final status

**Reviewed and ready for implementation planning.** No production code, deployment, data, or tests were changed by this research/review task.
