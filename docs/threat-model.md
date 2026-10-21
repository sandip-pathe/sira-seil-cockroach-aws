# Threat model

## Trust boundaries

1. Browser to API: authenticated sessions and signed, scoped requests; no database or OpenAI credentials reach the browser.
2. API/worker to CockroachDB: least-privilege service roles, tenant row-level security, database-time leases, fencing, and idempotent receipts.
3. API/worker to OpenAI: only the context needed for a typed decision or embedding is sent. Provider output is untrusted and validated before use.
4. Evidence files to application: content-addressed storage and checksums bind uploaded bytes to immutable database records. Current local storage is development-only.

## Main threats and controls

| Threat | Control |
|---|---|
| Cross-tenant access | CockroachDB row-level security, verified request identity, organization-scoped transactions, and negative isolation checks |
| Prompt injection in evidence | Treat evidence as data; validate typed output, citations, scope, and authority in deterministic code |
| Stale model result | Pin input versions, use leases and generation fences, and revalidate dependencies at finalization |
| Duplicate or interrupted work | Durable CockroachDB outbox, consumer receipts, effect keys, and retryable workers |
| Credential exposure | Server-side environment/secret manager, redacted logs, and credential scanning |
| Lost or altered evidence | Content hashes and immutable object identities; production requires a selected persistent storage backend |

Models can propose. Deterministic services and human approvals control business state and external effects.
