# SIRA/SEIL Decision Sprint — focused test plan

Scope: the P0 meeting-intelligence Decision Sprint defined in `docs/plans/JACK_AND_JILL_ARCHITECTURE_GAP_PLAN.md`.

This is a high-signal release gate, not a request for broad test theatre.

## Release invariants

1. Public catalogue data never contains buyer-private or seller-private fields.
2. Model output is never authoritative evidence without controlled capture and deterministic policy.
3. A repeated or concurrent request cannot duplicate spend, a Decision, outreach, publication, or payment effect.
4. A guest or tenant cannot read or mutate another tenant's private state.
5. Failure preserves the last verified artifact and one safe next action.
6. Research load cannot degrade checkout execution.

## Required proof by layer

### Domain/unit

- Catalogue version compiles into the existing graph candidate/evidence input.
- Unknown evidence remains unknown; absence does not become a negative claim.
- Demand compiler output is versioned and replayable.
- Input ordering and duplicate aliases do not change deterministic rank.
- Turn reservation handles replay, key/hash conflict, lease expiry, and stale mission version.
- Effect reservation requires exact payload hash, authority, expiry, and idempotency key.

### Controlled source capture

- Reject non-HTTPS, URL credentials, unsupported ports, and excessive redirects.
- Reject private, loopback, link-local, metadata, reserved, and rebound IPv4/IPv6 targets.
- Reject oversized or decompression-bomb bodies, MIME mismatch, unsupported archives, and parser-limit violations.
- Treat prompt injection and page instructions as text evidence only.
- Store final URL, content hash, exact locator, observed time, and source class.
- A search snippet alone cannot create a publishable claim.

### PostgreSQL/RLS/concurrency

- Public catalogue is readable without access to tenant-private source work.
- Cross-tenant research, draft, membership, Decision, and outcome reads or mutations fail.
- Two simultaneous turns cannot duplicate event sequence, tool work, or budget spend.
- Catalogue versions are immutable and current-pointer publication is compare-and-swap safe.
- Seller editor cannot approve their own publication; guest cannot claim, publish, contact, approve, or pay.

### Temporal/workers

- Decision and research workflows survive worker restart and activity retry.
- Cancel/resume returns the same run and preserves checkpoints.
- Exhausted budgets return `PARTIAL`, not fabricated completion.
- Worker loss and stale workflow IDs reconcile from PostgreSQL.
- Retained workflow histories replay with the promoted worker version.
- Workflow payloads contain IDs, hashes, and safe metadata only—no credentials, raw contracts/pages, prompts, or private source text.
- Saturating the research queue leaves the checkout queue healthy.

### API/effects

- Decision Sprint follows `202 -> RUNNING/PARTIAL -> COMPLETED` and safe failure states.
- Same idempotency key and same input returns the cached result; different input returns `409`.
- Vendor request binds exact Brief version, recipient, expiry, disclosure projection, and payload hash.
- Crash before or after provider dispatch reconciles to one external effect.
- Webhook replay cannot duplicate response, publication, outreach, or payment state.
- Missing optional capability reports one remediation and does not disable unrelated capabilities.

### Experience/accessibility

- “Hi” gets a short response, no tools, no agent-run panel, and no inspector opening.
- Clear request asks zero clarifications; ambiguous request asks at most one material question.
- Background work is safe to leave and returns through Inbox.
- Decision first viewport shows action, decisive uncertainty, and one next step.
- Feedback presents a proposed Brief diff before re-ranking.
- One-pane 320px flow has no page-level horizontal scroll.
- Keyboard focus enters and exits sheets correctly; automatic updates do not move focus.
- Failure keeps the latest verified Decision and puts technical trace behind details.

### End-to-end golden flow

1. An authenticated buyer submits a meeting-intelligence contract, invoice, or clear need.
2. A durable Decision operation appears within five seconds.
3. SIRA uses the database catalogue, not fixtures.
4. Missing decision-material evidence starts one bounded research run.
5. The first sourced partial appears without unsupported claims.
6. The existing decision graph produces incumbent/no-buy plus up to three comparable options.
7. The Decision explains evidence, uncertainty, company-stack effect, and counterfactual.
8. The buyer keeps, eliminates, or requests evidence; any recalibration is a visible Brief revision.
9. An optional vendor request sends once with exact sanitized scope.
10. An approval-ready brief is generated and an immediate outcome checkpoint is recorded.

## Migration/canary proof

- Expand migration works while the old API and worker remain live.
- Fixture-to-catalogue shadow inputs and results are diffed and reviewed.
- Feature flags `turn_v2`, `market_v2`, `research_v2`, and `effects_v2` can disable new work without deleting rows.
- One internal organization passes the golden flow before authenticated canary and guest rollout.
- Rollback stops workers or disables flags and leaves immutable records and outbox recoverable.

## Performance gates

- Decision Sprint accepted: p95 under 500 ms.
- Catalogue recall over 30 products: p95 under 150 ms.
- Deterministic evaluation: p95 under 750 ms after inputs freeze.
- Durable operation visible: under five seconds.
- First sourced partial: under 90 seconds when sources respond.
- Complete shortlist and action: under five minutes after required sources respond.
- Duplicate Decisions or effects under replay: zero.

## Ship gate

Ship the canary only when the release invariants, golden flow, cross-tenant negatives, concurrency and replay cases, controlled-fetch attacks, worker recovery, and migration rollback all pass. Broader categories remain blocked by the business expansion gate in the reviewed plan.
