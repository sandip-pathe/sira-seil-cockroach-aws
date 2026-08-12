# Build checklist

Status: reality reset on 2026-08-13. Only work present and verified in the root repository is marked complete.

## Build preferences

- **Mode:** Autonomous; continue through blockers and record deferred external checks.
- **Repository:** Work only in `D:\s\siel-n-sira` on `main`.
- **Git:** Focused local commits, then push to the canonical private remote as explicitly authorized.
- **Verification:** A task is complete only when its acceptance command passes or a clearly named external check is recorded as pending.
- **Product lock:** SIRA/SEIL stays the product. No memory rebrand or separate infrastructure demo.
- **Core cut line:** Tasks 1-9. Optional changefeeds, Lambda, Agent Skills, and multi-region work wait until the hosted proof passes.

## Checklist

- [x] **1. Preserve honest history and establish the canonical repository**
  Spec ref: `provenance.md > Source history`
  What to build: Restore the original August Git history, preserve the imported source commit, create one canonical repository, and mark the current hackathon boundary without rewriting dates.
  Acceptance: The original source commit is an ancestor of `main`; the boundary tag exists; the canonical remote and recovery bundle are recorded; the repository remains private during construction.
  Verify: `git merge-base --is-ancestor 8d917eba039b59b2c1a0f35d832093806101260c main`; `git show cockroachdb-hackathon-start`; `git remote -v`.

- [x] **2. Remove obsolete sponsor and runtime surfaces**
  Spec ref: `spec.md > 2. Reuse boundary`
  What to build: Remove DataHub, Senso, Snowflake, Temporal, PRAVA MCP/OAuth, the old PostgreSQL container/bootstrap runtime, imported PostgreSQL migrations, obsolete submission artifacts, and generated API routes. Keep SIRA/SEIL, auth, deterministic decision logic, and the narrow PRAVA hosted REST payment boundary.
  Acceptance: No active source/runtime reference to the removed technologies remains; the web and generated client pass; Python lint passes; the cleanup is committed and pushed.
  Verify: `rg -i "datahub|senso|snowflake|temporal|prava_mcp" --glob '!docs/hackathon-build/**' --glob '!uv.lock' .`; `corepack pnpm check:web`; `uv run ruff check python services tests scripts`; commit `f8db5e8` on `origin/main`.

- [ ] **3. Prove the CockroachDB compatibility slice**
  Spec ref: `spec.md > 15. Compatibility spike before migration`
  What to build: Add a pinned local CockroachDB container, driver/dialect, fresh Alembic baseline, and one representative tenant-owned table. Prove UUID/JSON, session tenant scope, RLS, representative idempotent writes, `VECTOR(1024)`, whole-callback SQLSTATE `40001` retries, conditional leases, and stale fencing-token rejection.
  Acceptance: A disposable real CockroachDB instance passes every compatibility assertion; no application transaction wraps a network/model call; the result is a reusable root module, not a side demo.
  Verify: `docker compose up -d --wait cockroach`; `uv run pytest tests/cockroach_integration/test_compatibility.py -q`; save a sanitized compatibility report.

- [ ] **4. Build the minimal authoritative CockroachDB schema**
  Spec ref: `spec.md > 4. Data model`
  What to build: Implement organizations, immutable buyer-context versions, seller-private pack versions, public catalog projections, separate context/catalog embeddings, missions, attempts, input refs, checkpoints, effects, outbox events, and decisions. Add one decision per mission and one replacement per invalidated attempt.
  Acceptance: Fresh migration creates only the vertical-slice schema; version heads advance without mutating history; buyer and seller authority boundaries pass; runtime and migration identities are separate.
  Verify: `uv run pytest tests/cockroach_integration/test_schema.py tests/cockroach_integration/test_tenancy.py -q`; migration smoke on a disposable database.

- [ ] **5. Add Bedrock embeddings and CockroachDB vector retrieval**
  Spec ref: `spec.md > 7. Retrieval and decision rules`
  What to build: Invoke `amazon.titan-embed-text-v2:0` at 1,024 dimensions, store model/dimension/content hash/source version, create separate context and catalog vector indexes, and rejoin candidates to authoritative current rows before deterministic gates.
  Acceptance: A real Bedrock vector is stored; tenant and publication filters cannot be bypassed; stale vectors are excluded; nearest-vector similarity cannot override an eligibility gate.
  Verify: `aws sts get-caller-identity --profile sira-hackathon`; Bedrock smoke; `uv run pytest tests/cockroach_integration/test_vector_retrieval.py -q`; record query plans and labeled retrieval results.

- [ ] **6. Implement version-safe evaluation, recovery, and idempotency**
  Spec ref: `spec.md > 5. Evaluation protocol`; `spec.md > 6. Worker leasing and fencing`
  What to build: Snapshot exact source versions in a short transaction, evaluate outside it, and finalize in a fresh retryable transaction. Invalidate stale attempts, insert/read one replacement, checkpoint durable work, reclaim expired leases with a larger fencing token, and suppress duplicate effects.
  Acceptance: The EU-available to US-only correction invalidates v1 with no decision; one v2 replacement completes; a stopped worker is resumed; the stale worker cannot finalize; ten duplicate deliveries create one effect and one decision.
  Verify: deterministic barrier tests for the evidence race, worker recovery, duplicate delivery, two stale finalizers, and retry exhaustion.

- [ ] **7. Compose the real SIRA/SEIL API and UI**
  Spec ref: `prd.md > FR11-FR13`; `design.md > Information architecture`
  What to build: Replace the transitional persistence wiring with Cockroach repositories, add `/health` and fail-closed `/ready`, expose buyer/seller mission APIs, and show the exact evidence correction, restart, recovery, recommendation, blocked option, versions, and collapsed run integrity inside the existing workspace.
  Acceptance: No fixture winner appears in hosted mode; a silent viewer understands the changed buying outcome before infrastructure details; PRAVA remains an optional human-approved hosted payment step.
  Verify: API tests, web check/build, keyboard and responsive checks, and one full local product journey against CockroachDB.

- [ ] **8. Deploy the API and two workers on AWS**
  Spec ref: `spec.md > 13. Deployment`; `CONFIGURATION.md > Credential groups`
  What to build: Provision a CockroachDB Cloud cluster, run the API and two workers on ECS/Fargate, use task roles for Bedrock, separate migration/runtime secrets, CloudWatch telemetry, and a public frontend pointed only at the hosted API.
  Acceptance: The hosted flow runs without local services or fixture fallback; two workers are visible; CockroachDB/Bedrock failures are explicit; secrets do not reach browser payloads or logs.
  Verify: hosted evidence-race/recovery/duplicate run, ECS task and role review, redacted CloudWatch trace, and a brief concurrent smoke test.

- [ ] **9. Prove Cloud MCP integrity and freeze submission evidence**
  Spec ref: `spec.md > 8. MCP integrity check`; `test-plan.md > 9. Release evidence`
  What to build: Configure a least-privilege external CockroachDB Cloud Managed MCP identity and validate five live invariants: all decision refs exist, versions match, invalidated attempts emitted no decision, duplicates made one effect, and the final worker held the current fencing token. Then prepare the README, architecture, video, screenshots, setup, disclosure, and evidence bundle.
  Acceptance: The verdict is visibly MCP-mediated and matches UI/SQL IDs; three hosted runs produce the same logical result; all public claims match stored evidence; license and pre-existing-work disclosure are clear.
  Verify: external MCP run, 3/3 hosted manifest pinned to the exact commit, clean setup smoke, secret/dependency scans, and manual rubric review.

## Optional after task 9

- Changefeed to an idempotent Lambda reevaluation trigger.
- Narrow CockroachDB Agent Skill proposal after checking existing work.
- Measured multi-region experiment.
- Live public product discovery outside the recorded path.
