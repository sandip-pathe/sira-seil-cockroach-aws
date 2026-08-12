# Build notes

## 2026-08-12 - planning and product lock

Deepening rounds: 0. The founder asked Codex to make implementation tradeoffs autonomously.

Founder direction:

- Keep SIRA and SEIL; reject a memory rebrand.
- Make CockroachDB causal to buying-decision correctness, not a decorative database swap.
- Use CockroachDB Distributed Vector Indexing and Cloud Managed MCP plus AWS Bedrock and ECS/Fargate.
- Keep PRAVA only as a narrow hosted payment/approval step.
- Remove DataHub because the self-hosted runtime is too large for this hackathon.
- Preserve honest project history and clearly disclose pre-existing work.

Locked demo: seller evidence changes from EU hosting available to US-only while SIRA is evaluating. The stale attempt emits no decision, one current replacement completes, a standby worker resumes after interruption, and duplicate delivery still produces one effect and one decision.

## 2026-08-13 - history and repository repair

- Restored the original August commit history into the root repository.
- Verified imported commit `8d917eba039b59b2c1a0f35d832093806101260c` is an ancestor of `main`.
- Preserved a local backup branch and verified bundle before history repair.
- Added `datahub-submission-final` and `cockroachdb-hackathon-start` boundary tags.
- Created canonical private repository `https://github.com/sandip-pathe/sira-seil-cockroach-aws` and pushed `main`.
- Deleted the abandoned nested `cockroach-build` repository. Its code and test results are not implementation evidence for the root product.

## 2026-08-13 - active-tree cleanup

Commit: `f8db5e8` (`chore: remove previous sponsor infrastructure`), pushed to `origin/main`.

Removed from the active root tree:

- DataHub code, infrastructure, proof routes/pages, scripts, screenshots, and submission material;
- Senso adapters, configuration, tools, UI copy, fixtures, and tests;
- Snowflake infrastructure, connector, decision routes, generated API contracts, fixtures, and tests;
- Temporal worker runtime and tests;
- PRAVA MCP/OAuth while retaining the hosted REST payment path;
- PostgreSQL Compose/bootstrap runtime and imported PostgreSQL Alembic chain;
- obsolete generated clients and old release scripts.

Retained:

- SIRA and SEIL product routes and workspace;
- Firebase/auth and buyer/seller authority concepts;
- deterministic decision logic and product-evidence flows that are not sponsor-specific;
- narrow PRAVA hosted checkout models/adapters;
- Apache-2.0 license and original history.

Verification:

- `corepack pnpm check:web`: passed.
- `uv run ruff check python services tests scripts`: passed.
- OpenAPI and TypeScript client regenerated successfully.
- 182 non-decision unit/API tests passed.
- Existing decision-fixture drift remains: ranking/cost expectations fail before Cockroach implementation and must be corrected separately, not hidden as a migration regression.
- Credential scan reports only inert short test literals in Git history; no current-tree credential finding was reported.

## 2026-08-13 - plan reality reset

Active shaping: the founder rejected continuing with stale numbered gates because substantial repository work had already happened outside them.

Changes:

- Replaced the old gate naming with nine plain milestones.
- Marked only history/repository repair and active-tree cleanup complete.
- Reopened every CockroachDB, vector, retry, worker, MCP, and AWS task because none exists in the root product yet.
- Removed all claims that the deleted side repository implemented the current product.
- Kept autonomous execution and focused commit/push cadence.

Next implementation target: the CockroachDB compatibility slice in the root repository.
