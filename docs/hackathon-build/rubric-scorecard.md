# Hackathon rubric scorecard

The current score reflects evidence available today. The target applies only after every core milestone passes on the hosted build.

## Product thesis

The strongest version is not “SIRA remembers.” It is:

> SIRA and SEIL can research, publish, and evaluate at the same time without producing a stale or duplicated buying decision.

CockroachDB creates asymmetric value through one combination: serializable state transitions, durable checkpoints, vector retrieval beside authoritative rows, idempotent effects, and a managed MCP inspection path.

## Score by criterion

| Criterion | Current | Hosted target | What earns the target | What would lose it |
|---|---:|---:|---|---|
| Agentic Memory Design | 4/10 | 9.5/10 | Buyer context, seller versions, research, mission checkpoints, events, effects, vectors, and decisions are durable and causally used; stale evidence invalidates a result that would otherwise be wrong | A chat-history table, toy CRUD, fixtures, or a database used only to save the final answer |
| Technical Implementation | 2/10 | 9/10 | Real distributed vector index, real Bedrock embeddings, short serializable transactions, 40001 retries, fencing, idempotency, scoped MCP integrity verdict, and deterministic race tests | Long transactions around model calls, vector-only decisions, hidden hard-coded outcomes, or generic PostgreSQL code with a CockroachDB URL |
| Real-World Impact | 6/10 | 8.5/10 | Direct buyer value: a corrected seller fact prevents an unsuitable shortlist; seller value: accurate, comparable evidence; clear AI/data-tool wedge | Generic procurement claims, no costly user problem, or infrastructure footage with no buying outcome |
| Production Readiness | 3/10 | 9/10 | Tenant isolation, authority boundaries, retry behavior, worker recovery, duplicate safety, traces, fail-closed hosted mode, and honest limits | Cross-tenant retrieval, fixture fallback, leaked secrets, unbounded retries, or “production-grade” language without tests |
| Creativity & Originality | 7/10 | 9/10 | A two-sided buyer/seller system shows why concurrent agent state needs database correctness, not just storage | Rebranding as a memory app, copying a standard RAG demo, or showing MCP as a chat-to-SQL trick |

Current evidence-backed total: **22/50**.
Target total: **45/50** only if every core milestone is demonstrated live.

## Why this can win

- The user problem is easy to understand before the infrastructure appears.
- The database changes correctness, recovery, and trust in the recommendation.
- The race is a causal proof: v1 would let the lower-cost option pass and win; v2 discloses US-only hosting, so the current evidence blocks it.
- The worker-stop and duplicate-event tests show agent behavior under real failure modes.
- SIRA and SEIL create a less common two-sided agent story than a personal assistant or generic RAG app.

## Fatal objections and answers

### “This is just a PostgreSQL app running on CockroachDB.”

Answer with the live outcome-changing evidence race, SQLSTATE retry handling, vector index, fenced worker recovery, duplicate suppression, and MCP integrity verdict. If those are absent, the objection is correct.

### “Why would a buyer trust the result?”

Every recommendation claim cites an immutable source version. Seller-published evidence and public research have different authority labels. Structured gates decide eligibility.

### “Why does this need multiple agents?”

Buyers update requirements, sellers publish product changes, research agents add evidence, and evaluation workers process missions independently. The concurrent update in the demo is a normal product event, not invented database theater.

### “Could CockroachDB build this internally in a day?”

CockroachDB can supply state, retrieval, and tools. It does not naturally own the buyer/seller product model, evidence authority boundary, cross-vendor evaluation, or purchasing workflow.

### “Is the market validated?”

No. The economic-value thesis is credible; willingness to pay is unvalidated. Do not confuse a strong problem hypothesis with proven demand.

## Required submission wording

State precisely:

- Distributed Vector Indexing retrieves tenant-scoped context and evidence candidates.
- A real external CockroachDB Cloud Managed MCP client reads the live mission and independently validates the decision state. Do not relabel an SQL result as MCP.
- The application uses CockroachDB as its authoritative state layer and handles serializable retries.
- ECS/Fargate runs the API and replaceable workers.
- Bedrock Titan Text Embeddings V2 creates the stored vectors.
- Changefeeds, Lambda, and an Agent Skill are optional and must only be named if implemented.

Avoid:

- “exact vector search”;
- “exactly-once changefeeds”;
- “MCP is read-only”;
- “global scale,” “zero downtime,” or “no reindexing”;
- “fully autonomous procurement”;
- “validated customer demand.”

## Judge verdict if we stop early

- Database connection plus CRUD only: 5/10, not competitive.
- Vector search plus saved chat history: 6.5/10, familiar RAG demo.
- Race-safe decisions but no recovery/MCP: 8/10, technically credible.
- Core milestones complete and visible: 9/10+ contender.
- Optional changefeed or accepted Agent Skill proposal: useful bonus, not a replacement for the core proof.
