# Jack & Jill comparison — verdict and continuation context

**Prepared:** 6 August 2026  
**Branch:** `Compare`  
**Purpose:** portable handoff for continuing the SIRA/SEIL architecture work on another machine.

## Start here

Read these files in order:

1. `verdict.md` — the decision and immediate next move.
2. `docs/plans/JACK_AND_JILL_ARCHITECTURE_GAP_PLAN.md` — full public research, repository audit, gap analysis, architecture, and CEO/design/engineering/DX reviews.
3. `docs/plans/JACK_AND_JILL_FOCUSED_TEST_PLAN.md` — high-signal implementation release gates.
4. `docs/plans/SEIL_AGENT_PARITY_AND_WEB_INGESTION.md` — existing SEIL parity and web-ingestion companion plan.

## What we were trying to learn

We used Jack & Jill as a structural reference for an elite two-sided agentic product—not as a UI to clone. The question was: what makes its experience feel intelligent and useful, what is publicly knowable about its system, and what remains for SIRA/SEIL to become a stronger commerce system?

Public evidence supports these conclusions:

- Jack & Jill is primarily a consented matching network, not a chatbot wrapper.
- It maintains durable candidate/role artifacts, searches continuously, progressively evaluates fit, learns from feedback, and introduces both sides only after mutual interest.
- Its public stack includes Next.js/TypeScript, FastAPI/Python, and PostgreSQL.
- Its exact ranking models, retrieval algorithms, queues, schemas, and production orchestration are private. Claims about those internals would be speculation.
- The defensible loop is longitudinal first-party intent + bilateral feedback + consent + outcomes + distribution—not a secret prompt.

The public agent guide and site can inform principles, but they are not evidence of the private product implementation and should not be copied as source or trade dress.

## Verdict

**Do not pivot SIRA/SEIL into a Jack & Jill clone. Preserve the Commerce Match OS destination and launch it through one buyer-first Decision Sprint.**

SIRA/SEIL already has unusually strong foundations:

- deterministic decision graph, evidence gates, bounds, ranking, and counterfactuals;
- versioned Product Evidence and seller publishing lifecycle;
- durable mission/tool concepts;
- RLS and isolated guest identity;
- explicit approval, effect, payment, and consent boundaries;
- Prava payment authorization and Temporal checkout composition.

The missing magic is not another agent framework. It is a trustworthy live-market loop that turns an actual buyer input into a materially better action, then learns from the outcome.

## Product shape we locked

- **Decision** is SIRA's canonical customer object.
- **Product** is SEIL's canonical customer object.
- Chat is the command surface, not the database or the product's final form.
- Missions, runs, tool traces, and model routing are diagnostics behind an information control; they never auto-open.
- The layout is a three-part grammar, not three permanently visible panes.
- A clear request asks zero clarification questions; an ambiguous request asks at most one question that can materially change the result.
- A completed Decision first shows the best-supported action, the uncertainty that could change it, and one safe next step.
- Guest research remains fast and isolated. Outreach, seller claim, publication, approval, and payment require authenticated authority.
- SIRA and SEIL share infrastructure but remain asymmetric buyer and seller agents.

## Locked implementation order

1. **Trust foundation** — real organization membership/capabilities, agent-turn reservation, universal protected effects, and database-enforced public/private boundaries.
2. **Live evidence** — controlled URL capture, immutable snapshots and claim drafts, a reviewed meeting-intelligence catalogue of roughly 20–30 products, and an independent research worker.
3. **Decision Sprint** — compile the database catalogue into the existing decision graph and return incumbent/no-buy plus at most three comparable options and an approval-ready action.
4. **Demand-triggered exchange** — one real email vendor request, normalized response, seller claim/review, and automatic re-evaluation.
5. **Calibration** — visible Brief revisions, feedback, outcome checkpoints, cost/quality traces, and measured ranking improvement.
6. **Marketplace expansion** — product-scoped SEIL, mutual consent, more connectors/channels, and additional categories only after evidence of demand.

## P0 architecture constraints

- PostgreSQL remains canonical; Temporal coordinates durable multi-step work and stores identifiers/hashes, not secrets, raw pages, private documents, prompts, or chain-of-thought.
- Separate decision, research, outreach, and checkout queues/workers so research failure or saturation cannot affect payment execution.
- Public catalogue versions are sanitized immutable projections. Buyer research and seller passports remain tenant-private and RLS-protected.
- Model output is untrusted until controlled capture, source attribution, deterministic policy, and required review.
- Reserve the agent turn before model/tool spend and reserve the exact effect before external dispatch.
- Reuse the existing decision engine, outbox, idempotency, evidence, authority, and workflow domains.
- Do not add a second decision engine, a general crawler, pgvector/search infrastructure, or a generic orchestration platform in P0.

## The first proof

Use the current meeting-intelligence vertical. A buyer supplies a clear need, contract, invoice, or renewal context. SIRA creates a durable Decision, researches only missing decision-material evidence, compares the incumbent/no-buy state with up to three products, and produces one supported next action. It can optionally send one sanitized vendor request after explicit authority. The user may leave while work runs and return through Inbox.

Expansion is blocked until there are at least 30 real missions across 10 organizations, 70% useful-result feedback, 40% vendor-request or approval-brief conversion, 10 vendor responses, five actual evaluations/trials/actions, and fewer than 10% material claim corrections.

## What remains uncertain

- Whether buyers take a materially better action than with general-purpose AI, review sites, and email.
- Whether the first category catalogue has sufficient evidence quality and recall.
- Whether vendor response and seller-claim loops create enough supply-side pull.
- Jack & Jill's private models, retrieval stack, production schema, workflow engine, and proprietary ranking logic.

These are validation questions, not reasons to replace the architecture.

## Current repository context

This branch starts at commit `83cf7e0` (`feat: refine agent workspace and document architecture`), which was also the local `Ui`/`snowflake-hackathon` checkpoint when the comparison branch was created. The comparison task changes documentation only. It does not deploy, alter production data, or claim that the P0 plan has been implemented.

The reviewed scores were CEO 8.1/10, design 9.0/10, engineering 8.6/10, and DX 8.9/10. Those scores describe plan quality after review—not product readiness.

## Next machine: first action

Before coding, compare this branch with the active implementation branch and confirm no newer schema/runtime work supersedes the dossier's repository audit. Then implement the trust foundation as one vertical slice: membership capability check -> agent-turn reservation -> protected effect reservation -> observable safe failure. After that, connect a small reviewed database catalogue to the existing deterministic graph. Do not start by redesigning chat or introducing another orchestration abstraction.

## Primary public references

- Jack candidate experience: https://www.jackandjill.ai/jack
- Jill hiring experience: https://www.jackandjill.ai/jill
- Jack & Jill company site and public pages: https://www.jackandjill.ai/
- Public agent guide: https://github.com/jackandjill-ai/agent-guide

The full dossier contains the source-by-source fact/inference/unknown ledger and should be treated as the authoritative research record.
