# SIRA + SEIL threat model

## Protected assets

- buyer needs, policies, budget signals, context, and conversation history;
- seller drafts, evidence sources, commercial constraints, and reservation values;
- released requirements/evidence, exact offer versions, approvals, and handoff receipts;
- model/runtime credentials, database roles, signing keys, and evidence objects;
- decision lineage, idempotency, fences, and effect uniqueness.

## Trust boundaries

1. Browser → FastAPI: Firebase or signed guest identity; browser headers never create production
   authority.
2. FastAPI/worker → CockroachDB: distinct non-owner roles, transaction-local tenant context, forced
   RLS, TLS in hosted mode.
3. Trusted service → AgentCore: short-lived signed ticket plus sealed context manifest; no SQL
   credential.
4. AgentCore → Bedrock: minimal authorized context and prefiltered schemas.
5. Seller private → exchange → buyer private: explicit release manifest and separate projections.
6. Cockroach outbox → SQS/worker: at-least-once transport with durable receipt/effect deduplication.

## Primary threats and controls

| Threat | Control | Executable evidence |
|---|---|---|
| Cross-tenant read/write | Server-derived tenant, validated transaction context, FORCE RLS, scoped FKs | foundation, API production-boundary, and Cockroach isolation tests |
| SIRA/SEIL private-context crossover | Principal/party invariant, reference data classes, separate tools/tickets/runtimes/projections | context, kernel-tool, runtime-ticket, and bilateral tests |
| Prompt injection from evidence | Evidence treated as data; strict output/tool schemas; deterministic grounding/authority; Bedrock Guardrail layer | Bedrock runtime and grounding tests; live Guardrail gate remains open |
| Model invents state or successful action | Strict discriminated decisions; code-owned transitions; durable tool/effect records | cognitive-kernel and run-engine tests |
| Tool escalation or argument smuggling | Pre-model filtering; contract version; `additionalProperties: false`; app-boundary checks | tool-broker and kernel-tool tests |
| Replay/stolen runtime request | Audience/principal/party/tenant/actor/purpose/tool/expiry binding plus nonce replay guard | runtime-ticket replay tests |
| Duplicate delivery/effect | Idempotency records, consumer receipts, semantic effect keys, unique constraints | Cockroach and outbox tests |
| Stale evidence or stale worker | Pinned versions/hashes, database-time lease, generation fence, final revalidation, one direct replacement | live evidence-race and worker tests |
| Approval changed after display | Offer/payload hash and version binding; expiry; single-use open receipt | approval, exchange, and handoff tests |
| Route capability disclosure | Authenticated participant check, encrypted opaque token, case/tenant/party/expiry binding | exchange-route and guest-bridge tests |
| Guest sees another guest | Per-session derived tenant and globally unique fixture identifiers | guest exchange API plus real-Cockroach live check |
| Secret leakage | Server-only configuration, Secrets Manager, sanitized reports/logs, credential scan | deployment preflight and credential scan |
| Queue/model outage loses input | Capture and checkpoint before long work; outbox; safe retryable failure | run-engine and worker recovery tests |

## Deliberate limitations

- A compromised trusted API database credential is outside RLS's protection boundary. Hosted
  mitigation is private networking, least-privilege non-owner roles, secret rotation, and audit.
- In-process guest rate limiting is per API task; production abuse protection also needs edge/WAF
  controls and measured distributed limits.
- Live IAM reachability, Guardrail intervention, AgentCore invocation, restore, canary, and log
  redaction remain deployment gates, not inferred claims.
- No payment is executed. The handoff proves approved intent and an external destination only.
