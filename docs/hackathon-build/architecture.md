# SIRA + SEIL qualified agent marketplace architecture

Status: approved on 2026-08-13. This is the repository architecture contract. The longer Office Hours record is retained outside the repository; this document contains the build-critical decisions.

## Product outcome

SIRA privately represents a software buyer. SEIL privately represents each seller. They exchange versioned minimum-disclosure projections to establish mutual fit, then humans approve one qualified introduction.

The P0 demo uses two meeting-intelligence products. The lower-cost product initially qualifies using seller evidence v1. SEIL publishes v2 while SIRA is evaluating it. CockroachDB must reject the stale attempt, create one direct replacement, produce one current decision citing v2, and prevent the outdated product from creating a match or introduction.

## Deployment topology

```text
Browser
  |
  v
CloudFront (public HTTPS edge)
  |
  v
private ALB through CloudFront VPC origin
  +-- /* ----------------------> Next.js web on ECS/Fargate
  +-- /v1/*, /health, /ready --> FastAPI on ECS/Fargate
                       |
                       v
             CockroachDB Cloud on AWS
             - authoritative business state
             - private context and shared operational state
             - Distributed Vector Indexes
             - versions, leases, fences, decisions
             - transactional outbox and effects
                       |
                       v
              dedicated ECS outbox dispatcher -> SQS FIFO + DLQ
                                                    |
                                                    v
                                      qualification ECS worker
                                      |
                         +------------+------------+
                         |            |            |
                         v            v            v
                  Bedrock Converse  Guardrails  Titan embeddings
                                      |
                                      v
                       fenced CockroachDB finalization

S3: immutable source bytes; CockroachDB controls identity/checksum/eligibility.
Managed MCP: read-only integrity views, never normal runtime transport.
CloudWatch/OpenTelemetry: sanitized correlated events and P0 metrics.
```

## Technology decisions

| Concern | Decision |
|---|---|
| Database | One CockroachDB Cloud Standard cluster on AWS, v25.4+, co-located with the application region. |
| Required CockroachDB tools | Distributed Vector Indexing for candidate retrieval; Cloud Managed MCP for independent integrity inspection. |
| Web/API hosting | CloudFront is the only public HTTPS edge. A VPC origin reaches one internal ALB, which routes to separate Next.js 16 and FastAPI ECS/Fargate services. Amplify is excluded because current SSR support ends at Next.js 15. |
| Agent runtime | Extend the existing typed SIRA/SEIL runtime with a Bedrock Converse adapter. Bedrock Agents Classic is excluded because it is closed to most new accounts. |
| Queue | Transactional CockroachDB outbox to SQS FIFO. SQS is delivery; CockroachDB remains authority and durable deduplication. |
| Documents | Encrypted, versioned, checksum-addressed S3 objects with interactive seller ingestion. CockroachDB stores immutable object identity and claim bindings. |
| Infrastructure | TypeScript CDK, per-task IAM roles, Secrets Manager and an exact-repository GitHub OIDC entry role. |
| Demo identity | API-issued signed HttpOnly guest session with an isolated Cockroach tenant per browser; Firebase is an optional upgrade path. Production never accepts development identity headers. |
| Payment | PRAVA is P2 after every P0 gate. Agents never hold payment credentials. |
| Multi-region/AgentCore/changefeeds | P2 experiments only after measured need and a green core. AgentCore Memory remains excluded. |

## Authority boundary

- Humans authorize evidence publication, consent, decision approval, contact disclosure and payment.
- Deterministic services validate, record and enforce authority.
- Models retrieve, extract, reason, critique, rank and propose. They cannot write authoritative commerce state directly.
- Buyer-private and seller-private records are structurally separated and use FORCE RLS. CockroachDB RLS derives the verified tenant from transaction-local `application_name`; principal/role capability remains server-validated. This is defense in depth against application mistakes, not protection after compromise of the runtime SQL credential: browser clients never receive that credential, the database is network-restricted, and the runtime identity is a non-owner without admin or `BYPASSRLS`. Shared embeddings contain only published buyer-safe projections.
- Hosted mode has no fixture, model, identity or stale-vector fallback.

## Context and durable state

| Kind | CockroachDB records | Validity |
|---|---|---|
| Semantic | buyer-context and buyer-safe catalog embeddings | DVI proposes; relational visibility/current-version gates decide use |
| Episodic | missions, attempts, checkpoints, observations and tool events | lease owner and generation fence determine the only writable attempt |
| Procedural | policy, prompt and tool-contract versions | runs pin explicit versions; changes never mutate historical behavior |
| Transactional | evidence, bundles, responses, consent, decisions, introductions and receipts | serializable constraints, hashes, unique keys and append-only events |

## Versioned business inputs

An immutable Product Bundle contains one Product Twin version, buyer-safe catalog projection, every evidence version eligible for retrieval, disclosure policy and embedding profile. Its ordered membership hashes produce a canonical digest. A product has one active bundle pointer.

P0 mission creation pins:

- active buyer-context version and hash;
- active Requirement Brief version and hash;
- procurement-policy version and hash;
- two active Product Bundle IDs and digests.

Retrieval is restricted to those bundles. Output citations must be a subset of eligible bundle evidence. Every accepted decision persists all dependencies, not only cited facts. A decision is current only while every invalidating dependency is still active.

Publishing is two phase. Validation, safe projection, bundle construction and embedding occur against a non-active candidate. One short transaction verifies every member/hash and human authority, then advances evidence, Product Twin, catalog, embedding and active-bundle pointers together. Failed embedding leaves the old bundle active. Retraction clears eligibility rather than serving old truth.

## Correctness kernel

1. The API writes domain state plus an outbox event in one short serializable transaction.
2. A worker claims an attempt using database time, lease expiry and an incremented generation fence.
3. It commits the exact input snapshot before retrieval or Bedrock/network work.
4. Checkpoint and finalization writes require the current lease owner and generation.
5. Finalization revalidates every input dependency in a new short transaction.
6. Changed input marks the attempt `STALE`, emits no decision/effect and inserts or reads one direct replacement using a unique constraint. Replacement chains are bounded to three; the demo produces one.
7. Valid input writes the decision, dependencies, citations, event and outbox reservation atomically.
8. SQLSTATE `40001` retries the entire deterministic callback in a fresh transaction/session with bounded jitter. No network or model call occurs inside it.
9. SQS deletion happens only after the database result commits. A durable consumer receipt makes redelivery harmless beyond SQS's deduplication window.
10. P0 introduction execution atomically revalidates current decision, both human consents, engagement digest and expiry, then writes one introduction/effect.

## P0 page contract

| Route | Backing state and action |
|---|---|
| `/sira` | buyer conversation, active brief and mission entry |
| `/sira/missions/[id]` | live attempts, engagements, decision and approval |
| `/seil/products/[id]/evidence` | preseeded v1/v2 evidence lineage and v2 publication |
| `/seil/opportunities/[id]` | buyer-safe requirement; seller returns `FIT`, `ANTI_FIT` or `NEEDS_INFO` and consents |
| `/matches/[id]` | dual consent and qualified introduction |
| `/integrity/[missionId]` | dependencies, vector candidates, fences, stale rejection, replacement and dedup proof |

Every P0 route covers loading, empty, partial, error, conflict/stale and success states. The controlled race uses a persisted `SNAPSHOT_COMPLETE` barrier available only in the isolated hackathon-demo deployment. Production infrastructure omits the controller route and IAM permission entirely.

## P0 gates

1. Real CockroachDB proves TLS SQL, fresh-session `40001` retry, pooled FORCE RLS, vector `EXPLAIN`, read-only Managed MCP and backup status.
2. Real Bedrock proves one pinned Converse model with typed tool use, Titan V2 at 1,024 dimensions and a Guardrail blocking the injection fixture.
3. The correctness kernel proves stale rejection, one direct replacement, lease takeover, duplicate delivery and one internal introduction.
4. Cross-tenant API/SQL/vector negatives pass using reused physical connections.
5. Six deployed routes complete five consecutive rehearsals without local or fixture state.

If the correctness kernel fails, shipping is blocked. Approach A is permitted only when the kernel, DVI/MCP and Bedrock are green but SQS or six-route integration is late; it uses database outbox polling and four consolidated screens, and the evidence must say which profile shipped.

## P1 and P2

Implemented P1 includes editable versioned company context, product portfolio management, interactive S3 ingestion, public DVI marketplace/product pages, durable buyer/seller inboxes, versioned settings/disclosure controls, safe DLQ operations, a credential-safe local restore verifier, a `ccloud` doctor and GitHub OIDC. Remaining P1 is hosted telemetry and Cockroach Cloud managed restore evidence.

Implemented P2 includes tenant-safe buyer/seller operational analytics derived from canonical records and transactional outbox events, explicitly labelled observational rather than causal. Remaining P2 is live PRAVA execution, Bedrock Automated Reasoning, AgentCore Runtime/evaluation experiments, measured changefeeds/multi-region, more categories and autonomous commercial operations only where authority and provider idempotency are proven.
