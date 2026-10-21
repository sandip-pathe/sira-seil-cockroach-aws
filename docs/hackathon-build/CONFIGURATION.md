# Configuration

## Credentials

| Setting | Used by | Rule |
|---|---|---|
| `OPENAI_API_KEY` | API and Python worker | Server-side secret; never expose to the browser |
| `DATABASE_URL` | API | Least-privilege CockroachDB runtime role |
| `SIRA_WORKER_DATABASE_URL` | Python worker | Worker role with only the required runtime grants |
| `SIRA_CATALOG_DATABASE_URL` | API and worker | Catalog role for vector retrieval and publication |
| `DATABASE_ADMIN_URL` | Migration process | Never pass to API, worker, browser, or logs |
| `EXCHANGE_ROUTE_SIGNING_KEY` | API | At least 32 bytes in production |

`.env.example` contains safe defaults and names only. Keep production identity credentials server-side and configure them through the selected host's secret manager.

## AI models

`OPENAI_CHAT_MODEL` selects the chat model; `OPENAI_EMBEDDING_MODEL` selects the embedding model. The catalog records its embedding model and vector width so retrieval cannot mix incompatible embeddings. Re-index the catalog when changing the embedding model.

## Health endpoints

- `/health` reports process health without secrets or private data.
- `/ready` checks the configured database schema and required runtime dependencies.

No production host or persistent evidence-file store has been selected yet. Local evidence storage is for development; choose durable storage before hosting.
