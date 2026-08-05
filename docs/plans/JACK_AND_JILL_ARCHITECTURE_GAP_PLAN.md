<!-- /autoplan restore point: C:\Users\sandi\.gstack\projects\siel-n-sira\Ui-autoplan-restore-20260806-025929.md -->
# Jack & Jill public architecture dossier and SIRA/SEIL build gap

- **Status:** Working plan before sequential CEO, design, engineering, and DX review
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

1. Keep one three-part workspace: object rail, conversation, contextual structured inspector.
2. Do not create a separate “decision room,” payment application, or agent-run dashboard.
3. Chat starts work; the inspector shows the current durable artifact only when useful.
4. Agent activity stays behind a response information control unless attention or authority is required.
5. Each decision/product has isolated context, history, task state, and canonical URL.
6. Recommendations show criterion-level evidence and uncertainty, not one opaque score.
7. Human actions are small and exact: keep, eliminate, need evidence, ask vendor, approve offer, authorize payment.
8. Background work returns through the inbox; users never need to watch a spinner for a long-running agent.
9. SIRA remains buyer language; SEIL remains seller language. The shared substrate never collapses the two roles into a generic assistant.

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
