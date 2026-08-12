# Verified technical references

Checked: 2026-08-12. Recheck before implementation and submission because product behavior and limits can change.

## CockroachDB Cloud Managed MCP Server

Source: [official Cloud MCP setup](https://www.cockroachlabs.com/docs/cockroachcloud/connect-to-the-cockroachdb-cloud-mcp-server)

- Managed HTTPS MCP endpoint for agents and coding tools.
- Supports schema inspection and queries; it also has write tools.
- Can be organization-scoped or pinned to a cluster.
- OAuth or service-account credentials inherit Cloud RBAC.

Project rule: use a cluster-scoped, read-only demo identity for bounded inspection. Use the SQL driver for application transactions.

## Distributed Vector Indexing

Sources: [vector indexes](https://www.cockroachlabs.com/docs/stable/vector-indexes), [VECTOR type](https://www.cockroachlabs.com/docs/stable/vector)

- Approximate-nearest-neighbor indexing with supported distance functions.
- Prefix columns can pre-filter, but queries must constrain every prefix column to exact values or supported `IN` values for the index to apply.
- Vector search is approximate and has accuracy/latency tradeoffs.

Project rule: exact tenant/authority prefixes first, ANN retrieval second, authoritative join and deterministic gates last.

## Serializable transactions

Source: [transaction retry errors](https://www.cockroachlabs.com/docs/stable/transaction-retry-error-reference)

- CockroachDB defaults to serializable isolation.
- Some retryable conflicts surface as SQLSTATE `40001` and require retrying the whole transaction.

Project rule: short snapshot transaction, external work outside, short validating finalization transaction.

## Changefeeds

Source: [changefeed message guarantees](https://www.cockroachlabs.com/docs/stable/changefeed-messages)

- Delivery is at least once.
- Duplicates can occur.
- First emissions preserve per-key ordering, not global or transactional ordering.

Project rule: optional consumer is idempotent and revalidates current authoritative state.

## Row-level security and worker locks

Sources: [row-level policies](https://www.cockroachlabs.com/docs/stable/create-policy), [`SELECT FOR UPDATE`](https://www.cockroachlabs.com/docs/stable/select-for-update)

- CockroachDB supports row-level policies.
- PostgreSQL parity must be tested, including documented upsert-policy limits.
- Row locks are not the sole correctness boundary for worker leasing.

Project rule: tenant tests for every write pattern; conditional lease update plus fencing token and serializability.

## CockroachDB Agent Skills

Sources: [official repository](https://github.com/cockroachlabs/cockroachdb-skills), [contribution guide](https://github.com/cockroachlabs/cockroachdb-skills/blob/main/CONTRIBUTING.md)

- Apache-2.0 repository with a proposal-first contribution process.
- Search existing work and get scope alignment before implementation.

Project rule: optional narrow diagnostic skill only after the core build passes. Claim the exact public state, not a hoped-for merge.

## Amazon Bedrock Titan Text Embeddings V2

Source: [Titan embedding models](https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html)

- Model ID: `amazon.titan-embed-text-v2:0`.
- Supports 1,024, 512, and 256 dimensions; 1,024 is the default.
- The vector database performs retrieval.

Project rule: use 1,024 dimensions and persist model ID, dimension, and content hash with every vector.

