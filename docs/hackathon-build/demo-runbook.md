# Judge demo runbook

Target length: 2:30–2:45.

Scenario: synthetic customer-support AI purchase. The buyer requires EU hosting.

Product labels: `privacy-safe option` and `lower-cost option`.

## What the video must prove

1. SIRA uses company context and evidence, not a generic web ranking.
2. SEIL publishes versioned seller evidence; public research is labeled separately.
3. A concurrent update cannot create a mixed-version recommendation.
4. A replacement worker resumes durable work.
5. Duplicate delivery does not duplicate the outcome.
6. CockroachDB vector retrieval and authoritative rows stay together.
7. Cloud MCP independently checks that the final state is internally consistent.

## Preflight

- Public frontend, API, two workers, CockroachDB Cloud, and Bedrock are healthy.
- Hosted mode has fixture fallback disabled.
- Demo database contains only synthetic buyer context, two seller packs, and labeled public research.
- The lower-cost seller pack is at v1 (`EU hosting available`) and the controlled v2 correction (`US only`) is ready but unpublished.
- Reliability controls are enabled only for the demo account.
- MCP identity is scoped to the demo cluster and configured read-only.
- Browser tabs: landing page, SIRA mission, SEIL product pack, and the real external CockroachDB MCP client/result.
- Browser console is clean; credentials, internal IDs, and unrelated missions are hidden.

Record the scenario ID, mission ID, trace ID, exact commit, reset time, initial seller-pack version, and initial decision/effect counts before capture. The reset command must target only `evidence-race` in the synthetic demo tenant.

## Screen sequence

| Time | Screen and action | What the viewer should understand | Later voiceover |
|---|---|---|---|
| 0:00–0:12 | Landing page. Enter as guest, then open SIRA. | This is a software-buying product, not a database dashboard. | “SIRA helps a company choose software. SEIL turns seller knowledge and public research into comparable evidence.” |
| 0:12–0:28 | Ask SIRA to choose a customer-support AI for the company. | The request is buyer-facing and specific. | “The answer has to fit this company’s systems, privacy rules, region, and budget.” |
| 0:28–0:45 | Decision inspector shows retrieved company constraints and candidate origins. | CockroachDB vector search found relevant tenant-scoped records; seller and research sources are distinct. | “SIRA retrieves relevant context and evidence from CockroachDB, then checks the authoritative versions and structured requirements.” |
| 0:45–1:02 | Start evaluation. Pause after snapshot v1. Switch to SEIL and publish the v2 correction from `EU available` to `US only`. | A seller corrects a business-critical fact while SIRA is working. | “While SIRA is evaluating version one, SEIL corrects the lower-cost option’s hosting region.” |
| 1:02–1:19 | Return to SIRA. The attempt changes to `Evidence changed; restarting`; v1 is invalidated and v2 is current. | The stale attempt that would have selected the cheaper option emitted no decision. | “The old evidence would pass the region gate and win on price. CockroachDB catches the new version before finalization, so SIRA restarts instead of making that bad decision.” |
| 1:19–1:36 | Stop the active worker after the next checkpoint. Show another worker resume. | The mission is durable and not tied to one process. | “Now one worker stops. Another claims the mission with a newer fencing token and resumes from the checkpoint.” |
| 1:36–1:49 | Replay the same event several times. The effect count and decision count stay at one. | Duplicate delivery is safe. | “The same event is replayed, but CockroachDB’s uniqueness boundary creates one effect and one decision.” |
| 1:49–2:08 | Final recommendation and blocked alternative. Open source details. | The privacy-safe option wins; the lower-cost option is blocked by the current EU-hosting requirement. | “SIRA recommends the option that still meets the company’s requirements. The cheaper option is blocked by its corrected US-only hosting limit.” |
| 2:08–2:18 | Briefly expand `Run integrity` in SIRA. This is the product-side SQL integrity summary. | The product records the race, recovery, and duplicate result without sponsor-specific copy. | “SIRA records the exact versions and whether the run remained internally consistent.” |
| 2:18–2:32 | Switch to the real scoped MCP client and run/show the five-check verdict over the same mission. | The second CockroachDB tool independently inspects live state. | “Separately, a scoped CockroachDB MCP client checks the same live mission and returns one verdict.” |
| 2:32–2:45 | Return to SIRA and hold on the final recommendation, EU requirement, v2 correction, and blocked option. | End on buyer value, not infrastructure. | “CockroachDB is not the product name. It is what lets these agents make one correct decision while they update, retry, and fail.” |

## Operator rules

- Do not show terminal startup, raw secrets, database passwords, or long JSON.
- Do not show DataHub, Snowflake, `/proof`, or old demo artifacts.
- Do not narrate fictional brand names.
- Do not say MCP is read-only; say the demo identity is configured read-only.
- Do not say vector search chooses the winner.
- Do not say exactly-once. Say duplicate delivery produces one effect through idempotency.
- Do not say multi-region, zero downtime, or production scale unless that exact footage exists.
- If the race, recovery, or duplicate proof fails, stop recording and fix it. Do not edit around a false result.

Expected status sequence: `READY -> SNAPSHOT_V1 -> EVIDENCE_CHANGED -> INVALIDATED_NO_DECISION -> RESUMING -> COMPLETE_V2 -> INTEGRITY_PASS`.

If recording is interrupted, do not continue an unknown run. Stop capture, save the trace ID, verify the current state, reset only the same scenario, and begin a new recorded run. Never delete or reseed shared data manually.

## Fallback footage

Use fallback footage only for a browser/rendering failure after the live proof already passed on the same commit. Keep:

- one clean final-decision screenshot;
- one race timeline screenshot;
- one recovery and deduplication screenshot;
- one expanded product-side Run-integrity screenshot and one real MCP-client verdict screenshot;
- one architecture diagram.

Label screenshots with the exact commit and capture time. A screenshot is not a substitute for the live concurrency and recovery test.
