# Architecture decisions

## CockroachDB owns durable workflow state

Runs, attempts, leases, checkpoints, receipts, and effects live in CockroachDB. The outbox is written in the same transaction as business state; the Python worker polls it directly. Model calls stay outside transactions, and finalization revalidates all pinned inputs.

## OpenAI is the model provider

The API and worker call OpenAI chat and embedding APIs through a provider adapter. The OpenAI SDK key is a server-side secret. Embedding records pin model identity and dimensions; model changes require a catalog re-index.

## LangGraph handles transient model retries

LangGraph wraps model calls with bounded retry behavior. It does not replace CockroachDB persistence, leases, fences, or idempotency.

## Evidence storage is a separate infrastructure choice

Development uses content-addressed local files and stores their identity/checksum in CockroachDB. A production deployment requires selecting persistent object storage independently of the model provider.

## Human authority remains explicit

Models may retrieve, reason, and propose. Deterministic application logic validates authority, while humans approve evidence publication, consent, decisions, and introductions.

## Public product knowledge persists across discovery requests

The shared marketplace stores canonical product identities and versioned public observations in
CockroachDB. SIRA uses OpenAI Responses web search when reusable observations cannot answer the
request. SEIL registrations stay private until the existing reviewed publication flow releases a
public projection. Research and seller publication retain separate provenance and freshness.
See [product-marketplace.md](product-marketplace.md) for the interfaces, source policy, and limits.
