# Test plan

The tests prove that CockroachDB changes correctness and recovery. Happy-path UI tests alone are not enough.

## 1. Unit tests

- canonical source and input-snapshot hashing;
- evidence authority labels and buyer-safe projection;
- embedding freshness checks for content hash, model ID, and dimension;
- deterministic eligibility gates and ranking;
- 40001 retry classification, limits, backoff, and jitter;
- lease expiry and fencing-token comparison;
- idempotency-key construction;
- user-facing error/state mapping;
- malformed model output rejection.

## 2. CockroachDB integration tests

Run against a real CockroachDB version matching Cloud as closely as practical.

### Tenant isolation

- tenant A cannot read tenant B context, packs, embeddings, missions, or decisions;
- buyer can read the public catalog projection but never seller drafts or private evidence;
- vector queries include exact tenant and authority filters;
- MCP demo identity cannot inspect another cluster or tenant scope;
- forced RLS applies to the application role;
- representative `ON CONFLICT` paths do not bypass or break policies.

### Versioning

- publish v1, then v2; v1 remains immutable and v2 becomes current;
- two concurrent publishers result in one valid current version or a handled retry;
- drafts and research evidence retain distinct authority states;
- completed input snapshots cannot be changed.

### Serializable retry

- force a transaction retry error and assert the whole transaction callback reruns;
- no external model or embedding call happens inside the retried transaction;
- retry exhaustion leaves a recoverable attempt with no partial decision.

### Vector retrieval

- create real 1,024-dimensional test vectors and the distributed index;
- verify query-plan/index use for the intended tenant-prefixed query;
- exclude stale hashes, wrong dimensions, retired sources, drafts, and other tenants;
- compare approximate retrieval quality with a small labeled synthetic corpus;
- prove deterministic rules can block the nearest vector candidate.

### Leases and effects

- only one worker claims a pending attempt;
- expired lease is reclaimed with a larger fencing token;
- stale worker checkpoint and finalization writes are rejected;
- ten duplicate events insert one effect;
- concurrent finalizers insert one decision.
- two concurrent stale finalizers create one replacement attempt;
- retry callbacks use stable IDs and a fresh session after SQLSTATE `40001`;
- leases use database time and tolerate skewed worker clocks;
- checkpoint resume does not repeat completed external calls;
- nested-savepoint idempotency and representative upserts are tested on CockroachDB;

## 3. Deterministic concurrency tests

Use barriers, not timing guesses.

### Evidence-race test

1. Worker A snapshots seller pack v1.
2. Test barrier pauses Worker A outside the transaction.
3. SEIL transaction publishes v2.
4. Worker A computes from v1 and tries to finalize.
5. Finalization detects v2, marks A invalidated, and emits no decision.
6. Worker B or a new attempt snapshots v2 and completes.

Assertions:

- no decision references a mix of v1 and v2;
- invalidated attempt is preserved for inspection;
- exactly one current final decision exists;
- repeat 100 times with zero violations.

### Worker-stop test

1. Worker A checkpoints after retrieval.
2. Stop Worker A or terminate its task.
3. Let its lease expire.
4. Worker B claims with a larger token and resumes.
5. Restore Worker A and attempt a stale finalization.

Assertions:

- B completes from durable state;
- A receives `LEASE_LOST`;
- one effect and one decision exist;
- recovery time meets the 20-second demo target.

### Duplicate-delivery test

- replay one event 10 times serially and concurrently;
- assert one effect, one outbox result, and one decision;
- callers receive the existing result or a safe no-op.

## 4. Optional changefeed tests

- duplicate webhook messages are deduplicated;
- consumer re-reads current version before enqueueing;
- events for different keys may arrive without global ordering assumptions;
- Lambda retry does not duplicate reevaluation;
- database outage leaves a retryable event, not a lost one.

## 5. API tests

- buyer can start and inspect only own missions;
- seller draft/publish transitions enforce seller authority;
- SIRA receives published buyer-safe fields only;
- research-only items are visibly labeled;
- invalidated attempts never appear as final recommendations;
- hosted mode rejects missing CockroachDB and Bedrock configuration;
- health endpoints do not return secrets;
- MCP is not exposed as an unrestricted public proxy.

## 6. UI and accessibility tests

- loading, empty, error, success, evidence-change, recovery, and stale-evidence states;
- recommendation remains primary; infrastructure details remain secondary;
- source origin and exact version are readable;
- keyboard focus reaches mission, decision, and inspector controls in order;
- status changes use an appropriate live region without repeated announcements;
- 360 px, 768 px, 1440 px, and reduced-motion checks;
- no horizontal overflow and no hidden critical status below an inaccessible pane;
- no DataHub/Snowflake/proof copy survives in the new build.

## 7. Hosted end-to-end tests

- create mission from public frontend;
- verify a real CockroachDB row and Bedrock vector;
- publish evidence during evaluation and observe invalidation;
- with two workers running, stop the active ECS worker and observe standby lease takeover/resume;
- replay a duplicate event and observe one effect;
- inspect state through the Cloud Managed MCP Server;
- prove the inspection actually used MCP rather than relabeled SQL;
- verify final decision versions match across UI, SQL, and MCP;
- deny CockroachDB temporarily and confirm the app fails closed;
- review CloudWatch logs for trace continuity and secret leakage.

## 8. Performance checks

Measure with synthetic data and report dataset size:

- vector retrieval p50/p95;
- mission-state read p50/p95;
- transaction retry count and latency;
- recovery time after worker termination;
- duplicate suppression latency;
- end-to-end decision time;
- 10 simultaneous demo users.

No scale claim may exceed the tested dataset, concurrency, topology, or duration.

## 9. Release evidence

For the exact submission commit, save a sanitized bundle containing:

- test summary;
- evidence-race timeline;
- worker recovery timeline;
- duplicate-event counts;
- vector retrieval query and labeled results;
- final source refs and hashes;
- MCP inspection match;
- hosted URLs and health checks;
- screenshots and video timestamp map;
- dependency and secret-scan results.

The bundle must not contain credentials, buyer-private text, full prompts, raw embeddings, or database connection strings.

## 10. Setup, configuration, and upgrade tests

- clean Windows setup reaches the documented doctor/up/reset/run/verify path;
- clean Linux setup reaches the same path without PowerShell-only assumptions;
- missing, expired, and wrong-scope SQL, AWS, Firebase, and MCP credentials produce a named cause and next action without printing values;
- logs, doctor output, API errors, evidence bundles, and browser payloads contain no secrets;
- reset refuses a missing scenario, wildcard, production tenant, or another demo run;
- migration upgrades from the prior supported head on a disposable CockroachDB database;
- partial migration failure leaves a documented recoverable state;
- `/health` stays process-focused while `/ready` fails closed for required dependency/schema failures.
