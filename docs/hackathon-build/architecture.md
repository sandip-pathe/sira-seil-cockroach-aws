# Current architecture

SIRA helps a buyer compare software against its needs and seller-published evidence. SEIL helps sellers maintain that evidence. Humans retain authority over publication, consent, decisions, and introductions.

## Runtime

```text
Next.js web app -> FastAPI -> CockroachDB
                         |       - business state, tenant isolation, vectors
                         |       - durable outbox, leases, checkpoints, receipts
                         v
                    OpenAI API

Python worker -> CockroachDB outbox -> validated work -> CockroachDB
Local evidence uploads -> content-addressed filesystem; SQL stores identity and checksum
```

The API and worker use OpenAI chat and embedding APIs. LangGraph retries transient model failures; CockroachDB remains authoritative for durable workflow state, fencing, and idempotency. The worker polls the outbox directly, so no external queue is required.

## Authority and state

- Humans authorize evidence publication, consent, decision approval, contact disclosure, and payment.
- Deterministic services validate and record authority. Models can retrieve, reason, and propose; they cannot commit business effects directly.
- Buyer-private and seller-private records use CockroachDB row-level security. Browser clients never receive database credentials.
- Vector search proposes candidates; relational visibility and current-version checks decide whether they may be used.
- Evidence, bundles, responses, decisions, introductions, and receipts are versioned and auditable.
- Network/model work stays outside database transactions. Finalization revalidates inputs and commits under a current lease and generation fence.

## Hosting boundary

No production hosting platform or persistent evidence-object store has been selected. Local filesystem evidence storage is for development only. Choose a host and persistent storage before deploying; OpenAI supplies model APIs, not application hosting, database, or file storage.
