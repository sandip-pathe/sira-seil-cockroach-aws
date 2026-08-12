# Product requirements — SIRA + SEIL CockroachDB build

Status: draft for build approval  
Owner: SIRA + SEIL team  
Target: CockroachDB × AWS Hackathon

## Product statement

SIRA helps a company choose software—and keeps the decision valid when requirements or product facts change. SEIL turns seller knowledge and public research into comparable product evidence. CockroachDB keeps the agents’ shared work correct when evidence changes, jobs retry, or workers fail.

## User problem

A software buyer can ask an agent for a recommendation, but the answer is weak if it forgets company constraints, mixes old and new seller claims, cannot separate public research from seller evidence, or loses progress after a failure.

The buyer needs one answer with a clear reason and exact sources. The seller needs a controlled way to publish accurate product evidence. Both need the system to remain correct while several agents work at once.

## Main user journey

1. The buyer opens SIRA and asks for a customer-support AI that fits the company.
2. SIRA retrieves relevant company context and prior decisions.
3. SIRA requests current product packs from SEIL and includes clearly labeled public research.
4. The buyer sees the work in progress: company context, product evidence, evaluation, and decision.
5. If a product fact changes a requirement or result, SIRA invalidates the unfinished attempt and restarts with the newer version.
6. If a worker stops, another worker resumes from the last durable checkpoint.
7. SIRA returns one recommendation, blocked alternatives, and the reasons for both.
8. The buyer opens the decision details and sees the exact evidence versions used.

## Seller journey

1. A vendor opens SEIL and creates or updates a product pack.
2. SEIL separates claims, proof, fit rules, anti-fit rules, integrations, limits, and commercial details.
3. The vendor reviews and publishes a new immutable version.
4. Published evidence becomes available to SIRA; drafts do not.
5. If the update affects an active evaluation, the stale evaluation is invalidated and rerun.

## Public research journey

1. SIRA finds too few seller-published products for the buyer’s request.
2. A previously captured public source supplies one research-only listing in the core demo; live discovery remains a later product path.
3. SEIL stores research-only listings with source URL, capture time, and confidence.
4. SIRA can compare them, but the UI never calls them seller-attested.
5. A vendor can later claim and replace a research listing with a reviewed seller pack without rewriting history.

## Epics and user stories

### E1 — Buyer-specific selection

As a software buyer, I want SIRA to compare products against my company’s actual requirements so that the recommendation is useful to this company, not a generic ranking.

Acceptance: the final decision shows the requirement that determined eligibility, the recommended option, the blocked alternative, and the evidence origin.

### E2 — Seller correction without stale decisions

As a vendor, I want SEIL to publish a corrected product fact without rewriting the old version so that active and completed evaluations remain explainable.

Acceptance: publishing v2 preserves v1, invalidates an unfinished v1 evaluation, and triggers one replacement attempt using v2.

### E3 — Durable agent work

As a buyer, I want an interrupted evaluation to continue safely so that a worker failure does not lose work or create a second answer.

Acceptance: the standby worker resumes from the checkpoint, the stale worker cannot finalize, and one mission produces one decision.

### E4 — Independent integrity inspection

As an evaluator, I want a scoped CockroachDB MCP client to inspect the live mission so that I can verify the versions, invalidation, deduplication, and worker authority without trusting the product UI alone.

Acceptance: the real MCP-mediated check returns the same IDs and versions shown in SIRA and passes all five invariants.

## Functional requirements

### FR1 — Company context

- Store company requirements, constraints, tools, and prior decision notes as versioned records.
- Create a Bedrock Titan embedding for retrievable text.
- Keep the structured fields authoritative.
- Let the buyer correct or retire a context item.
- Never expose buyer-private context to a seller.

### FR2 — Seller product packs

- Preserve draft, review, published, and superseded states.
- Create a new version for every published change.
- Keep proof and limitations next to each claim.
- Expose only the published, buyer-safe projection to SIRA.

### FR3 — Research-only listings

- Store the source URL, capture time, extracted claims, and confidence.
- Label every research-only item in SIRA.
- Do not let research evidence silently overwrite seller evidence.

### FR4 — Candidate retrieval

- Use tenant-scoped CockroachDB vector search to retrieve relevant company context and product evidence.
- Use exact tenant and status filters before ranking.
- Reject stale embeddings whose source hash or model version no longer matches.
- Treat vector results as candidates, not proof of fit.

### FR5 — Decision input snapshot

- Record the exact buyer-context IDs and versions, seller-pack IDs and versions, research IDs and versions, model versions, and retrieval query used for every evaluation attempt.
- Compute a stable hash for the snapshot.
- Never mutate a completed snapshot.

### FR6 — Concurrent evidence change

- Detect when a referenced source is no longer current before finalizing a decision.
- Mark the attempt `INVALIDATED` and create a new attempt from current evidence.
- Never show an invalidated attempt as a recommendation.
- Show a short user-facing note: “Evidence changed. SIRA restarted this evaluation with the latest version.”
- In the core demo, seller pack v2 changes EU hosting from available to unavailable, blocks the lower-cost option, and changes the final recommendation.

### FR7 — Worker recovery

- Save a checkpoint after each durable mission step.
- Claim work with a lease, attempt number, and fencing token.
- Let another worker resume expired work.
- Prevent the stopped or delayed worker from finalizing after its lease is lost.
- Show “Resumed after a worker interruption” in demo mode.

### FR8 — Idempotency

- Require an idempotency key for every externally visible agent effect.
- Enforce uniqueness in CockroachDB.
- Replaying an event must return the existing result or a safe no-op.
- A duplicate must never create a second final decision.

### FR9 — Recommendation

- Rank only eligible products.
- Explain why the winner fits the company.
- Explain why an alternative was blocked.
- Show evidence origin and freshness.
- Store the exact decision input snapshot and output hash.

### FR10 — CockroachDB MCP integrity check

- Configure a least-privilege MCP identity scoped to the demo cluster.
- Let an external, scoped MCP client read the mission, checkpoint, evidence versions, retry/invalidated attempts, effects, fencing token, and final decision.
- Return one pass/fail verdict for: all decision references exist; every version matches the final snapshot; no invalidated attempt emitted a decision; duplicates produced one effect; and the finalizing worker held the current fencing token.
- Keep normal application transactions on the SQL driver.
- Do not claim that MCP is read-only; configure it read-only for this demo.
- Do not label an in-product SQL integrity summary as MCP output. Show MCP inside SIRA only if that payload actually traveled through MCP end to end.

### FR11 — Hosted operation

- Run the API and replaceable workers on AWS ECS/Fargate.
- Use Bedrock for embeddings.
- Use CockroachDB Cloud as the only database for the hackathon path.
- Fail visibly if CockroachDB or Bedrock is unavailable.
- Never switch to fixture mode in the hosted demo.

### FR12 — Demo controls

- Add a demo-only reliability section inside the existing SIRA decision inspector.
- It may trigger an evidence race, stop the active worker, and replay one event.
- It must be hidden unless the hosted app is started in demo mode.
- Do not create a separate proof, memory, or infrastructure page.

### FR13 — Decision hierarchy

- Order the inspector as Outcome → What changed → Company requirements → Compared options → Evidence and versions → Run integrity.
- Keep Run integrity collapsed by default.
- Make the recommendation and blocked alternative the largest elements.
- Show the exact seller-field diff before worker, transaction, or MCP details.
- Keep chat updates short enough that the final result is not buried.

## User-visible states

| Surface | Loading | Empty | Error | Success | Partial/recovery |
|---|---|---|---|---|---|
| Company context | “Finding relevant company context…” | Ask for one requirement | Explain retrieval failure; retry | Show selected constraints | Show missing optional context |
| Product evidence | “Checking seller and public evidence…” | Explain that no usable products were found | Name which source failed | Show origin and freshness | Continue with labels if only research evidence exists |
| Evaluation | Show current step | Not applicable after start | Explain retryable or blocked state | Show recommendation | “Evidence changed; restarting” |
| Worker recovery | No separate loader | Not applicable | “Evaluation could not resume” | Hide when uneventful | “Resumed after interruption” |
| Decision details | Load exact source refs | Explain missing decision | Do not show an unverified result | Show versions and decision hash | Mark invalidated attempts as history only |
| Run integrity | “Checking decision integrity…” | Explain no mission exists | Explain database-check failure | Show `PASS` and product-side checks | Show the failed check and a direct next action |

The judge-visible external MCP check has its own ready, authentication/scope error, partial-result, and pass/fail states; it does not control the recommendation.

The transition from v1 to v2 must announce once through an accessible live region. No state may rely on green/red color alone.

## Privacy and authority rules

- Buyer context is buyer-private.
- Seller drafts are seller-private.
- Only published, allowlisted seller evidence crosses to SIRA.
- Public research remains `RESEARCH_ONLY` until a seller reviews and publishes it.
- Embeddings carry the same tenant and authority boundary as their source row.
- Agent text is never permission. The server decides what each agent can read or write.
- A recommendation is advice. Purchase or contract actions require a human.

## Non-functional requirements

- Correctness: zero mixed-version final decisions in the concurrency test.
- Recovery: resume an interrupted evaluation within 20 seconds in the demo environment.
- Deduplication: ten replays of one event produce one effect and one decision.
- Traceability: 100% of recommendation claims link to a versioned source.
- Retrieval: all vector queries apply exact tenant and evidence-status filters.
- Security: no cross-tenant rows in API, SQL, vector, or MCP tests.
- Reliability: client retry loop handles CockroachDB SQLSTATE `40001` with bounded exponential backoff and jitter.
- Accessibility: new states work with keyboard, focus order, status announcements, and existing responsive layout.
- Observability: every mission, attempt, event, checkpoint, and decision shares a trace ID.

## Measures

### Demo acceptance

- Evidence version changes during a live evaluation.
- First attempt becomes invalidated.
- Replacement worker resumes the mission.
- Duplicate event is suppressed.
- One final decision cites the current complete evidence set.
- A real external MCP client returns the same IDs and versions shown in SIRA and the five-check verdict passes.
- Seller pack v2 changes a real eligibility gate and the final recommendation.

### Submission proof points

- **Agentic memory design:** buyer context, seller evidence, checkpoints, attempts, effects, and decisions survive process failure and remain version-linked.
- **Technical implementation:** real vector retrieval plus real scoped MCP inspection; structured gates remain authoritative.
- **Real-world impact:** one corrected seller fact prevents a cheaper but incompatible purchase.
- **Production readiness:** tenant boundaries, serializable retries, fencing, idempotency, fail-closed hosted mode, and traceable recovery are demonstrated.
- **Creativity:** SIRA and SEIL work concurrently across a buyer/seller boundary without mixing evidence generations.

### Product signals after the hackathon

- time from request to usable shortlist;
- percentage of recommendation claims with evidence;
- number of blocked unsuitable products before a paid proof-of-concept;
- number of evidence changes that trigger reevaluation;
- buyer corrections to retrieved company context;
- renewal or replacement decisions influenced by prior outcomes.

These are proposed metrics, not validated results.

## Acceptance boundary

The feature is not accepted if the demo uses hard-coded winner text, precomputed race outcomes, an in-memory checkpoint, two databases for authoritative state, or a vector result as the final decision.
