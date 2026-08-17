# SIRA + SEIL architecture decisions

Status: accepted for the flagship build on 2026-08-18. These decisions describe the implemented
system. Live AWS and Cockroach Cloud claims still require hosted evidence.

## ADR-001: CockroachDB owns durable truth

**Decision.** CockroachDB is the sole authority for tenant data, conversations, cognitive runs,
checkpoints, evidence versions, decisions, exchange state, approvals, idempotency, outbox events,
consumer receipts, and effect records. S3 owns immutable evidence bytes, while CockroachDB owns
their identity, checksum, version, visibility, and business use.

**Why.** Buyer, seller, worker, and retry activity can overlap. Serializable transactions, unique
constraints, version checks, fencing generations, forced RLS, and one outbox authority prevent a
stale model result or duplicate delivery from becoming a second business fact.

**Consequence.** AgentCore Memory, LangGraph checkpoints, SQS, caches, and model context may not
become competing state authorities. They can accelerate or transport work only.

**Evidence.** Migrations through `cdb0018`, `persistence.database.Database`, the qualification and
bilateral repositories, and `tests/cockroach_integration`.

## ADR-002: A small typed kernel, not a graph framework

**Decision.** One bounded loop performs capture → assemble → decide → authorize → execute →
checkpoint → compose. The provider returns one strict `TurnDecision`; code owns transitions.

**Why.** The current graph is small, while its difficult part is the trust boundary around durable
state and tools. A second orchestration persistence layer would add recovery ambiguity without
solving a measured problem.

**Consequence.** Reconsider LangGraph only when several reusable branching subgraphs cannot be
expressed cleanly. Reconsider Temporal only when external waits/compensation exceed the tested
outbox state machine. Any adapter must continue to store authority in CockroachDB.

**Evidence.** `sira_api.cognitive_engine`, `sira_agents.kernel_models`, and run-engine tests.

## ADR-003: Models propose; deterministic code authorizes

**Decision.** Models may interpret, ask questions, propose typed reads, and compose explanations.
They cannot set persistent status, authorize disclosure, perform ranking arithmetic, consume an
approval, or claim an effect succeeded.

**Why.** Model output is probabilistic and untrusted. Commercial authority requires stable replay,
exact hashes, roles, versions, and auditable denial.

**Consequence.** Tool schemas reject extra fields. The broker filters by principal, party, purpose,
stage, risk, version, schema, budget, and exact capability. Application services repeat decisive
authorization. Current model-visible tools are reads; human/API commands own mutations and the
provider-neutral handoff.

## ADR-004: SIRA and SEIL are separate principals

**Decision.** SIRA is always buyer-side; SEIL is always seller-side. They share kernel code but not
private context, policies, tool catalogs, runtime tickets, AgentCore audiences, IAM identity, or
budgets. Exchange data crosses only through compiled party projections.

**Why.** A two-sided agent marketplace is credible only if one prompt or compromised runtime
cannot observe both reservation values and both private histories.

**Consequence.** Context validation rejects opposing private references. Runtime tickets bind
principal, party, tenant, actor, purpose, audience, tools, nonce, and expiry. AgentCore receives no
database credential.

## ADR-005: AgentCore is a stateless model boundary

**Decision.** AWS defines separate SIRA and SEIL AgentCore Runtime resources. They validate a
signed manifest and call Bedrock Converse. The trusted API persists the input and accepts only a
typed result.

**Why.** This provides workload/IAM isolation and managed execution without moving business truth
or tool authority into an opaque agent service.

**Consequence.** AgentCore Memory is intentionally absent. A runtime outage leaves the durable run
recoverable. SIRA alone retains the bounded synthetic experiment contract; it is evidence, never
commercial authority.

## ADR-006: Bilateral exchange is a deterministic protocol

**Decision.** Buyer and seller submit append-only commands to a deterministic coordinator. Each
party reads its own projection through an opaque, expiring route capability. Offers are immutable,
counteroffers point to a predecessor hash, and approval binds the exact current offer.

**Why.** Free-form agent-to-agent chat cannot prove ordering, disclosure, acceptance, or what a
human approved.

**Consequence.** V1 is deliberately 1:1. It ends at an immutable, expiring, provider-neutral
external handoff. SIRA never holds payment credentials or reports payment success.

## ADR-007: The current interface is frozen

**Decision.** No route, layout, component, type, spacing, color, motion, or interaction is changed
without founder approval of a visual proposal. Backend wiring and nonvisual correctness fixes must
preserve rendered output.

**Why.** The restored interface is the product baseline and previous redesign work reduced product
quality.

**Consequence.** See `ui-preservation-review.md`. Architecture work must fit behind existing
surfaces; documentation is the venue for future UI proposals.
