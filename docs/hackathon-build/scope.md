# Scope — SIRA + SEIL on CockroachDB and AWS

## One sentence

SIRA helps companies choose software—and keeps the decision valid when requirements or product facts change. SEIL supplies seller-attested and public evidence; CockroachDB keeps those independent agents on one correct, durable state while they work concurrently.

## Problem

Software evaluation is assembled from incompatible pieces:

- buyer requirements live in documents, calls, old decisions, and people’s memory;
- seller claims change over time and are hard to compare;
- public research is useful but is not seller-attested;
- several agents can research, publish, and evaluate at the same time;
- a crash or retry can duplicate work or produce a recommendation from stale evidence.

Today buyers reconcile spreadsheets, security questionnaires, vendor decks, calls, and public research manually. When one fact changes, they rarely know which recommendation must be redone. They need a recommendation tied to their company and to the exact evidence that was current when the decision was made.

## Users

### Primary buyer

An IT, operations, security, data, or procurement lead choosing an important B2B tool.

### Primary seller

A product, sales engineering, or solutions lead who wants the product represented accurately and compared on evidence rather than marketing language.

### Evaluator persona

A judge or developer who needs to verify that concurrent updates, failure, recovery, retrieval, and deduplication are real. This is not a market user.

## Demo scenario

A company asks SIRA to choose a customer-support AI.

Buyer requirements include an existing CRM integration, EU hosting, a budget, and a rule for handling customer data. SEIL has two seller-published product packs plus one seeded, sourced, research-only listing.

During evaluation, the lower-cost option corrects its seller pack from “EU hosting available” in v1 to “US only” in v2. Under v1 it would pass and win on price. SIRA invalidates that stale attempt before it can emit a decision, resumes after a worker failure, blocks the lower-cost option on the current EU-hosting requirement, and recommends the privacy-safe option with exact source versions.

All companies, products, prices, claims, and test inputs are synthetic.

## In scope

1. Existing SIRA and SEIL chat workspaces, with the existing sidebars and decision inspector.
2. Company context, seller product packs, and public research as separate evidence types.
3. Immutable evidence versions and a decision input snapshot.
4. CockroachDB as the system of record for missions, checkpoints, evidence, embeddings, events, and decisions.
5. Distributed vector indexing for candidate retrieval inside the same database as the authoritative evidence rows.
6. Short serializable transactions with client retry handling.
7. Lease plus fencing-token worker recovery and idempotent event handling.
8. AWS-hosted API and agent workers.
9. Amazon Bedrock Titan Text Embeddings V2 for 1,024-dimensional evidence and context embeddings.
10. A scoped CockroachDB Cloud Managed MCP integrity agent that independently checks the live decision state and returns pass/fail.
11. One deterministic live “evidence race” and one worker-stop recovery demonstration.
12. A build provenance ledger and an honest pre-existing-work disclosure.

## Optional after the core demo passes

1. A CockroachDB changefeed that triggers reevaluation after seller evidence changes.
2. An idempotent AWS Lambda consumer for that changefeed.
3. A narrow `diagnosing-agent-memory-integrity` Agent Skill and a public proposal/PR to the official skills repository.
4. Multi-region failure testing, only if it can be executed live and measured.

## Not in scope

- Rebranding SIRA or SEIL around memory.
- A generic “AI memory” dashboard.
- A separate `/proof` or `/memory` product page.
- Autonomous purchasing, payment, contract signature, or cancellation.
- Claiming public research is vendor-approved.
- Claiming vector similarity decides eligibility or the winner.
- Keeping PostgreSQL as a second source of truth for the hackathon path.
- Porting DataHub proof adapters, Snowflake flows, production activation, or rollback routing.
- Pretending reused SIRA/SEIL code was created during this hackathon.
- Multi-region or billion-vector claims without a live benchmark.

## Required CockroachDB and AWS use

### CockroachDB tools

1. Distributed Vector Indexing — retrieves company context and candidate evidence.
2. Cloud Managed MCP Server — a scoped agent inspects the live mission, source versions, retries, checkpoint, and final decision.
3. Agent Skills Repo — optional third tool after the core flow passes.

### AWS services

1. Amazon ECS/Fargate — runs the API and replaceable agent workers.
2. Amazon Bedrock — creates Titan Text Embeddings V2 vectors.
3. AWS Lambda — optional changefeed consumer.

## Success conditions

The build is complete only when:

- the same user mission survives a worker replacement;
- a duplicate event cannot create a duplicate effect or decision;
- a seller update during evaluation cannot yield a mixed-version decision;
- the v2 seller correction changes a hard eligibility result and therefore the final recommendation;
- vector retrieval returns relevant tenant-scoped candidates, while structured gates determine eligibility;
- every final claim cites a stored evidence version;
- the MCP integrity check returns `PASS` for source versions, invalidation, fencing, and duplicate suppression;
- the app fails visibly if CockroachDB is unavailable instead of falling back to fixtures;
- the full demo works from the hosted application in less than three minutes.

## Build assumptions to verify

- The selected CockroachDB Cloud plan and region support the intended vector index and scoped MCP setup.
- The imported RLS and write patterns pass a real CockroachDB compatibility spike.
- Bedrock Titan Text Embeddings V2 is enabled for the chosen ECS task role and region.
- Two pre-running workers can demonstrate lease takeover within the measured demo target.
- The EU-available to US-only correction changes structured eligibility; otherwise the scenario is rejected, not cosmetically narrated.
- Public guest controls can be limited to one synthetic tenant and scenario without general infrastructure authority.

## Product value

For buyers: less evaluation work, fewer unsuitable shortlists, and a decision that can be checked later.

For sellers: a structured way to show where a product fits and where it does not.

For both: fewer arguments based on stale decks, forgotten constraints, or uncited chatbot answers.

This is a strong economic-value hypothesis. Willingness to pay and adoption are still unvalidated.

The frequency of stale-evidence failures and sellers’ willingness to maintain structured packs are also unvalidated. The demo proves technical and product plausibility, not market demand.
