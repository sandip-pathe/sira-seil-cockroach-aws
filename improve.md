# SIRA + SEIL Executable Proof Exchange: hackathon audit and improvement plan

> **Positioning correction:** “DataHub-native admission agent” is rejected. The DataHub Agents feature already provides the agent shell, external tools, triggers, decisions, and run history. That framing turns this project into a feature DataHub can reproduce quickly. The product is the cross-company executable proof exchange; a DataHub agent is only one buyer-side runtime component.

**Audited:** 10 August 2026
**Audit baseline:** local `main` at `d0db26f`; fetched remote default branch `origin/main` at `95310b5`; `improve.md` is the audit-created worktree change
**Scope:** repository, proof code, UI, release artifacts, focused tests, build, current DataHub capabilities, and the published hackathon rubric. Deadline timing is intentionally excluded.

## Decision

**The core proof is real. The exchange and submission are not finished. Do not submit the current public repository as-is.**

The strongest part is unusually strong for a hackathon: DataHub is causal, authoritative, and written back to. The proof reads live graph context, turns it into executable gates, runs identical trials, changes the winner when one governed fact changes, binds approval and activation to an exact artifact digest, verifies routed behavior, writes a receipt core hash and historical projection to DataHub, finds the core hash through a fresh MCP session, and restores state.

The weakest part is that this is still a fixed reference scenario rather than a bilateral exchange transaction. The target assets, policy, candidates, prices, adapter behavior, and approving actor are predetermined. The two sellers are local demo images, not independent SEIL endpoints. The live demo bypasses seller publication and the durable proof repositories that exist elsewhere in the codebase. There is no real buyer-created campaign, seller response, human approval, continuous invalidation, purchase/provisioning gate, or production deployment target.

The submission itself has hard blockers:

- Local `main` is **11 commits ahead** of the freshly fetched remote default branch; `origin/main` still presents the old generic Seilnsara marketplace.
- The 3/3 release evidence is pinned to `a11ad35`, while current HEAD is `d0db26f` after two behavior-changing UI fixes.
- `.artifacts/` is gitignored, so the proof bundle and screenshots do not ship to judges.
- The exact CI static checks currently fail: 5 Ruff lint errors, 22 unformatted files, and 12 mypy errors.
- No DataHub-specific public video or completed Devpost submission package is present in the repository.
- Setup requires Windows, PowerShell, Docker Desktop, Node, Python, `uv`, and roughly 8 GB for DataHub Quickstart.

### Current hard score

| Criterion | Score | Judgment |
|---|---:|---|
| Use of DataHub | **8.5/10** | Causal graph use, MCP reads and mutations, ownership, lineage, structured properties, receipt writeback, and fresh-session core-hash lookup. |
| Technical execution | **6.5/10** | Strong deterministic proof and recovery; reduced by stale release evidence, red CI, fixed orchestration, and disconnected persistence. |
| Originality | **7.0/10** | The cross-company protocol thesis is novel, but the current demo fabricates both seller projections inside one buyer process; generic read-act-approve-write orchestration is not original. |
| Real-world usefulness | **5.5/10** | The pain is credible, but there is no configurable practitioner workflow, real seller release, non-synthetic/customer graph, or demand evidence. |
| Submission quality | **4.0/10** | Clear proof README and polished UI, but the public repo is stale and the evidence/video do not ship. |
| Open-source bonus | **0** | No upstream DataHub connector, skill, fix, RFC, or documentation contribution was found. |

**Overall: 31.5/50, or 6.3/10.** This is a credible entry after release repair, but not winner-ready yet. New positioning alone earns no points. The same architecture can become an 8+/10 entry if it becomes one real cross-company campaign instead of a fixed harness.

### Verification snapshot

- Focused proof tests at current HEAD: **18 passed**.
- Current web production build: **passed**.
- Apache-2.0 license and explicit pre-existing-source provenance: **present**.
- Exact repository static checks: **failed** with 5 Ruff lint errors, 22 files needing formatting, and 12 mypy errors.
- Local release artifact: **3/3 passed** with one semantic result hash, but only for commit `a11ad35`.
- A broader agent-run test selection also exposed provider isolation: local OpenAI keys changed one expected test path. Test fixtures must clear `OPENAI_API_KEY`, `SIRA_OPENAI_API_KEY`, and `SEIL_OPENAI_API_KEY`.

Most static-check failures are in the broader inherited application rather than the proof kernel. That protects the narrow technical claim, but not submission quality: the published workflow still runs those checks and will be red.

## What was actually built

The runnable code is a **DataHub-powered proof and deployment kernel for AI/data-tool releases**:

`graph context -> executable manifest -> equivalent trials -> deterministic decision -> exact authority -> verified effect -> DataHub receipt -> recovery`

Genuinely implemented:

- Pinned DataHub MCP reads of schemas, lineage, ownership, tags, and structured properties.
- Stable double-read of decisive context before accepting an observation.
- A deterministic compiler that turns graph facts into executable eligibility gates.
- Two digest-pinned adapter containers with no network and read-only roots receiving the same synthetic trial. They are not yet safe for hostile seller code because the proof containers share one writable socket volume.
- A reproducible `B -> A -> B` winner flip caused by one PII-tag mutation, plus an unrelated-tag negative control.
- A minimum-disclosure seller-to-buyer projection contract.
- Hash-bound approval checks for owner, context, manifest, decision, projection, digest, expiry, and revocation.
- Compare-and-set route activation, health verification, routed traffic, rollback, and a pre-write injected compensation scenario.
- A DataHub Decision document containing the receipt core hash and historical projection, followed by a fresh-session search that finds the core hash. The current code does not parse and compare the saved projection; the complete immutable receipt remains local.
- PostgreSQL/RLS models and integration tests for buyer projections, approvals, effects, and insert-only receipt cores.
- A polished operator workspace and a 3/3 deterministic release bundle for commit `a11ad35`.

Not implemented as a live exchange workflow:

- A buyer opening a campaign for a governed asset, job, policy, budget, or candidate set.
- Two independent sellers receiving the same minimum-disclosure contract and returning release-bound offers.
- A seller publishing an adapter through the product and having that publication consumed by the proof.
- An authenticated DataHub owner reviewing and approving a pending request.
- A genuinely adaptive AI agent or bounded planning/tool loop in the proof path.
- Live proof persistence through the PostgreSQL proof repository.
- A proof receipt gating a real purchase, provisioning action, vendor contract, or external customer environment.
- Continuous metadata-drift detection and automatic requalification.
- A searchable proof history or reusable proof across environments.

## Product lens

### The problem

The problem is not merely “software purchasing is hard,” and it is bigger than checking one release:

> Enterprise AI and data software is bought through claims, questionnaires, staged demos, and bespoke PoCs. None creates a comparable, release-bound proof that the product works inside the buyer's actual governed environment. Buyers cannot disclose their graph to every seller; sellers cannot rebuild a custom PoC for every buyer; and yesterday's approval becomes unsafe when either the buyer graph or seller release changes.

The status quo produces three failures at once:

1. **Trust failure:** the buyer is asked to trust seller claims instead of a buyer-specific execution result.
2. **Comparability failure:** competing releases are not tested against the same contract, canary, environment fingerprint, and success criteria.
3. **Memory failure:** the result is left in tickets and screenshots, so the next buyer, owner, or agent cannot safely inherit it.

The underlying practitioner pain is credible. Commercial demand for this exact exchange is still unproven. The repository contains no hackathon-specific user interviews, design partners, paid pilots, or evidence that a buyer and seller have agreed to use this protocol.

### Locked positioning

> **SIRA + SEIL is the executable proof exchange for enterprise AI and data software. A buyer's private DataHub graph is compiled into a minimum-disclosure evaluation contract. Competing sellers submit exact release-bound SEIL adapters. The exchange runs equivalent trials, compares technical and commercial outcomes, gates the chosen purchase or deployment, and issues a portable proof receipt. When the buyer graph or seller release changes, the proof expires and the market reruns.**

Short version:

> **The neutral trial and clearing network where enterprise AI/data software earns the right to be bought and deployed.**

SIRA is the buyer-side campaign and decision agent. SEIL is the seller-side release agent and executable offer. DataHub is the buyer's private context and institutional-memory layer. The neutral exchange protocol, trial infrastructure, release identity chain, and cross-company network are the product.

This is not a generic software marketplace. Search results, lead generation, checkout, and payments do not create the core value. The atomic transaction is:

`private buyer graph -> minimum-disclosure contract -> comparable seller offers -> neutral execution -> authorized outcome -> purchase/deployment gate -> portable receipt -> requalification`

Primary hackathon category: **Open / Wildcard**, with **Agents That Do Real Work** as a secondary category once SIRA and SEIL perform real bounded tool loops. Do not put an LLM at the eligibility, approval, or effect boundary. Agents may interpret intent, discover assets, negotiate missing evidence, and assemble a campaign; the proof kernel remains deterministic.

### The wedge and the 10-star product

The first category should be **third-party AI tools that need access to governed customer or operational data**. It has visible risk, frequent release changes, difficult buyer-specific compatibility, and a natural DataHub dependency.

The first complete transaction is deliberately narrow but still an exchange:

- one buyer campaign;
- one governed workload;
- two independently published seller releases;
- one incumbent/no-buy baseline;
- one identical hidden canary;
- one real owner approval;
- one purchase/provision/deploy gate;
- one receipt written to DataHub and returned to the winning seller.

The 10-star version is a clearing network, not a larger agent:

- Buyers publish privacy-safe evaluation contracts derived from private context graphs.
- Sellers maintain conformant SEIL adapters and signed release evidence once, then answer many qualified campaigns.
- The exchange runs hidden, equivalent trials in neutral execution cells.
- Proof receipts are portable but scoped: exact release, environment class, policy version, graph dependencies, expiry, and outcome.
- A seller release or buyer graph change invalidates only affected proofs and creates a requalification market.
- Accumulated verified outcomes make future trials faster and harder to game.
- Procurement and deployment systems accept the receipt as machine-verifiable authority.

Single-release admission remains a useful enterprise module and fallback. It is not the company, the headline, or the hackathon's originality claim.

### Why DataHub cannot build the product in one line

DataHub Agents already supports custom instructions, DataHub tools, external MCP plugins, scoped views, scheduled/on-demand tasks, human decisions, and run history. DataHub MCP already supports search, identity, lineage, metadata mutations, proposals, and documents. Therefore **“an agent reads DataHub, calls a seller, pauses for approval, and writes a result” has no defensible novelty**.

| Layer | DataHub already provides | SIRA + SEIL must provide |
|---|---|---|
| Intra-company context | Search, schema, lineage, ownership, tags, policies, views | Buyer graph compiled into a versioned minimum-disclosure contract without exposing the graph |
| Agent runtime | Instructions, tools, external MCP plugins, tasks, decisions, audit trail | Bilateral buyer and seller agents operating under a neutral protocol |
| Seller participation | An external tool can be called | Seller identity, signed release offers, adapter conformance, evidence expiry, and a reusable SEIL standard |
| Execution | An agent can invoke a tool | Identical hidden trials in isolated cells with anti-gaming and hostile-code boundaries |
| Decision | A human can answer a question | Multi-vendor technical/commercial comparison plus incumbent/no-buy and deterministic eligibility |
| Authority | Metadata can be mutated or proposed | Tested = offered = selected = approved = purchased = activated digest binding |
| Memory | Documents and metadata can be written back | Portable, scoped proof receipts shared across buyer, seller, procurement, and deployment systems |
| Compounding value | One organization's graph gets richer | Cross-company adapter ecosystem, outcome history, category benchmarks, and requalification network |

The hard counterfactual is simple:

- Remove DataHub and the buyer-specific evaluation contract, causal eligibility result, owner authority, and requalification trigger disappear.
- Remove SIRA + SEIL and DataHub still has an agent runtime, but no seller network, neutral trial standard, comparable offers, clearing transaction, or portable proof market.

That mutual necessity is the product boundary.

Official capability references: [DataHub Agents](https://docs.datahub.com/docs/features/feature-guides/agents), [DataHub MCP Server](https://docs.datahub.com/docs/features/feature-guides/mcp), [Agent Context Kit](https://docs.datahub.com/docs/dev-guides/agent-context/agent-context), and [hackathon rules](https://datahub.devpost.com/rules).

### Users

| Role | Job in this product | Current implementation |
|---|---|---|
| AI/Data Platform Engineer | Open a proof campaign, define the workload, and connect the result to deployment | Only a fixed local run button and CLI |
| Procurement/FinOps Lead | Compare qualified offers, commercial terms, and the incumbent/no-buy option | Missing |
| Application or ML Engineer | Request a capability against a governed asset and consume the winning tool | Missing |
| Data Owner | Review affected assets and authorize one exact purchase/deployment effect | Contract exists; human workflow missing |
| Security/Privacy Reviewer | Inspect sensitivity, residency, lineage, seller evidence, and trial isolation | Read-only proof output only |
| Vendor Solutions/Release Engineer | Publish a signed SEIL adapter, release evidence, price/SLA, and remediation response | API field/outbox projection partial; no usable UI or conformance SDK |
| Seller Product/Revenue Lead | Compete on verified fit rather than generic claims and reuse proof across campaigns | Missing |
| Head of Data/AI Platform or CDO | Economic buyer; reduce review time and unsafe deployments | Value proposition unvalidated |
| Hackathon judge/local developer | Run and inspect the fixed proof | This is the only complete user today |

### Status quo

The buyer currently writes requirements, reads DataHub manually, copies facts into Jira/Slack and security questionnaires, watches incomparable vendor demos, creates one-off PoCs, chases owners in another system, negotiates price without verified fit, deploys through a separate platform, and leaves the result in screenshots. Each seller repeats a different bespoke solutions-engineering exercise. SIRA + SEIL turns those disconnected activities into one comparable, executable transaction.

### Approaches considered

| Approach | Effort | Strength | Fatal weakness | Decision |
|---|---:|---|---|---|
| A. DataHub-native admission agent | Small | Fastest route from current code to a complete single-release workflow | DataHub Agents already supplies most of the visible product shell; weak originality and no cross-company compounding value | **Reject as positioning** |
| B. Multi-vendor executable proof campaign | Medium | One complete buyer/seller transaction is demoable, causally DataHub-dependent, and clearly beyond a stock agent | Requires real seller publication, neutral execution, dynamic campaign setup, and authority | **Build for the hackathon** |
| C. Full proof clearing network | Large | Strongest company, protocol, and network moat; proofs improve future transactions | Too much to make all marketplace, trust, portability, and commercial rails real in one hackathon build | **Use as the product horizon** |

Recommendation: build **B as a real vertical slice of C**. Do not ship A and describe C in slides. The demo must contain the bilateral transaction that makes C believable.

### Defensibility

The moat is not an agent prompt, DataHub MCP integration, approval UI, hashes, or a Decision document. Those are reproducible components.

The credible moat, in order, is:

1. **N-by-M interoperability:** one seller release works across many buyer contracts and one buyer contract evaluates many sellers without bespoke code.
2. **SEIL adapter ecosystem and conformance standard:** sellers publish once and remain continuously qualifiable.
3. **Category-specific hidden canary library:** neutral tests become better at detecting gaming and false fit.
4. **Verifier trust and portable receipt standard:** procurement and deployment systems accept a narrowly scoped signed result.
5. **Buyer and seller distribution:** DataHub, procurement, cloud marketplace, CI, and deployment integrations bring both sides into the same rail.
6. **Consented outcome history:** only after real volume exists, verified release/context/outcome evidence improves future campaigns.

Do not claim an outcome-data moat yet. Initial results will be sparse, private, and confounded.

### Product kill tests

1. **Network or bespoke PoC?** Two buyer context profiles must evaluate the same two seller releases without buyer-specific or seller-specific code changes.
2. **Will sellers participate?** One real vendor or open-source maintainer must publish through the conformance path in under one hour and receive a concrete reuse benefit.
3. **Are unlike products comparable?** The contract must compare category outcomes, not force identical internal APIs. If each candidate needs custom test design, this becomes consulting.
4. **Does minimum disclosure hold?** Raw DataHub topology, hidden policies, source data, budgets, and competitors' offers must stay buyer-local.
5. **Is the proof honest?** A receipt says an exact release passed named tests under an exact context until expiry. It never certifies universal safety or compliance.
6. **Can vendors game the canary?** Hidden randomized cases, immutable signed releases, post-deployment outcomes, suspension, and disputes must make gaming costlier than real conformance.
7. **Is DataHub actually causal at useful depth?** The result must depend on multi-hop lineage, sensitivity, ownership, contracts/assertions, and the agent/service graph—not one decorative PII tag.

## Exchange workflow coverage

| User workflow | Status | Evidence | What is missing |
|---|---|---|---|
| Open a buyer proof campaign | **Missing** | Fixed constants in `python/proof/constants.py` | Requester, business job, target asset, scope, budget/terms, candidate set, incumbent/no-buy option |
| Discover governed context | **Partial** | `python/proof/datahub_mcp.py` reads fixed entities and lineage | MCP search, arbitrary URNs, configurable traversal, multi-owner blast radius, quality/incidents/contracts |
| Compile a minimum-disclosure evaluation contract | **Implemented for one case** | `python/proof/manifest_v0.py` | Privacy budget, policy packs, explainable source links, versioned user-defined gates, unsupported-context handling |
| Invite or discover eligible SEIL sellers | **Missing** | Two fixed local candidates in `exchange_demo.py` | Seller registry, category/capability matching, transport, campaign invitation, deadline and response state |
| Publish and sign a release-bound offer | **Partial/disconnected** | Seller service stores `proof_adapter` and emits a buyer-safe projection | Independent seller endpoint, signed price/SLA/terms/evidence, conformance run, artifact retrieval, expiry/suspension; live demo still uses `_published_projection` constants |
| Run equivalent containerized trials | **Strongly implemented for trusted demo images** | Digest-pinned containers, no network, read-only roots, same canary | Hostile-code isolation, real workloads, richer gates, latency/load behavior, multiple tool protocols |
| Clear a winner or no-buy outcome | **Strongly implemented for fixed candidates** | Decision Graph, gate results, price tie-break, B-A-B counterfactual | True no-buy baseline, configurable valuation, commercial terms, uncertainty, human reject/override, independent seller inputs |
| Review the causal result | **Partial** | Polished `/proof` workspace | Side-by-side B/A/B snapshots, direct DataHub entity links, raw trial result drill-down, why each gate exists |
| Obtain transaction authority | **Contract only** | Wrong-owner/stale/digest/expiry/revocation cases block | Pending request, authenticated owner and procurement authority, `get_me`/group proof, explicit approve/reject, separation of duties |
| Gate procurement, provisioning, or deployment | **Implemented only for a local route effect** | CAS router, health, routed traffic, digest identity, rollback | Purchase/provisioning authority, Kubernetes/feature flag/MCP gateway target, real service, durable idempotent job state |
| Write and find receipt projection | **Partial** | DataHub document anchor, projection write, fresh-session grep for the core hash | Parse exact document content, compare projection, recompute hash, structured status on agent/service/release, aspect versions, expiry |
| Return a portable receipt to buyer and seller | **Missing** | Local immutable receipt is not a cross-company protocol artifact | Signed scope, allowed disclosures, environment class, evidence audience, revocation/expiry, seller delivery and reuse rules |
| Persist campaign and proof history | **Architecture only** | RLS models and integration-tested repositories | Live orchestration uses JSON artifacts and in-memory process state instead of repositories |
| Recover from failure | **Implemented narrowly** | Pre-write injected branch issues no receipt and manually verifies rollback | Inject a real MCP write failure, prove exception-triggered rollback, durable retries/reconciliation, operator-visible recovery |
| Requalify after buyer or seller drift | **Missing** | Manual button/CLI only | DataHub change subscription, seller release events, stale receipt, blast radius, read-only recheck, fresh authority only when outcome changes |

## Why DataHub use is meaningful

DataHub is not a connector badge here:

1. Schema, lineage, tags, structured properties, and ownership become executable policy inputs.
2. Mutating one DataHub PII fact changes the evaluation contract and winning offer while candidate code and other inputs stay fixed.
3. A seeded required owner group observed in DataHub is included in the exact effect subject.
4. Success is not declared until the receipt core hash and historical projection are written and the core hash is found through a fresh MCP session. Exact projection comparison is not yet implemented.

That is stronger than most “metadata-aware” demos. A JSON fixture cannot replace the asserted live mutation, stable context read, ownership check, writeback, and fresh-session lookup without changing the product's trust model.

However, DataHub already ships the generic primitives: context retrieval, external tools, human decisions, metadata mutation, scheduled/event execution, and tool-call audit. A generic “procurement agent reads DataHub, calls a seller tool, asks for approval, and writes a document” is therefore easy for DataHub or another team to reproduce. The originality must be the protocol DataHub does not provide:

- cross-company minimum-disclosure proof exchange;
- equivalent isolated trials over exact release artifacts;
- graph-derived executable evaluation contracts that disclose requirements without disclosing the buyer graph;
- independently published, signed, release-bound seller offers;
- tested = offered = selected = approved = purchased = healthy = active digest binding;
- comparable technical and commercial clearing against an incumbent/no-buy baseline;
- compare-and-set activation and routed-behavior verification;
- compensation and portable historical receipts;
- counterfactual selection and requalification when buyer context or seller releases change;
- a cross-company adapter and outcome network that compounds beyond one DataHub tenant.

Relevant current surfaces: [hackathon rules](https://datahub.devpost.com/rules), [resources](https://datahub.devpost.com/resources), [MCP Server](https://docs.datahub.com/docs/features/feature-guides/mcp), [DataHub Agents](https://docs.datahub.com/docs/features/feature-guides/agents), [Agent Context Kit](https://docs.datahub.com/docs/dev-guides/agent-context/agent-context), [DataHub Skills](https://github.com/datahub-project/datahub-skills), [Agent Registry](https://docs.datahub.com/docs/features/feature-guides/agent-registry), and [Service Catalog](https://docs.datahub.com/docs/features/feature-guides/service-catalog).

## Fatal judge objections

1. **“This is a scripted integration test, not an exchange.”** True today. Fixed URNs, candidates, prices, test input, and behaviors predetermine the state space.
2. **“The owner never approved anything.”** True today. `seeded_support_owner` and its DataHub owner mapping are created in code; the subject is immediately asserted and consumed.
3. **“The seller never published a real release.”** True in the live proof. Seller publication code exists, but the demo reconstructs both projections in memory.
4. **“The durable architecture is theater.”** Partly true. PostgreSQL/RLS repositories are integration-tested, but the operator path reads the latest generated JSON artifact and keeps runner state in one API process.
5. **“This is not yet a purchasing exchange.”** Correct. The current build is its qualification kernel. Do not claim a completed transaction until a valid receipt gates procurement, provisioning, or deployment authority.
6. **“Why could DataHub not build this in a day?”** It could build the generic agent shell. Unless the demo proves independent seller endpoints, a neutral protocol, equivalent hidden trials, exact offer-to-effect identity, and a portable receipt crossing organizational boundaries, this objection remains fatal.
7. **“Would buyers and sellers participate?”** Unknown. There is no demand evidence, non-synthetic/customer graph, independent seller, or observed buyer/seller workflow yet.
8. **“Can I reproduce what I watched?”** Not from the current public repository. It is 11 commits behind, the evidence is ignored, CI is red, and the release bundle is from an older commit.
9. **“Is the receipt reusable historical truth?”** Only partially. It is a generic Document and does not capture exact DataHub aspect/system-metadata versions for point-in-time replay.
10. **“Is DataHub actually live?”** The UI label is hardcoded. It can say `DataHub live` without a live health/read check, and the local bundled screenshot still shows a pre-fix historical-state label.
11. **“Can an untrusted seller image attack the proof runtime?”** The current adapters and router share one writable socket volume with unauthenticated Unix sockets. No-network and read-only roots are useful, but they do not establish a hostile-code security boundary.

## Improvements

### P0 — make the submission truthful and judgeable

1. Push the reviewed DataHub commits to the public repository. Confirm the public default branch contains the exact submitted commit.
2. Fix the five Ruff errors, format the 22 files, fix the 12 mypy errors, and require the GitHub workflow to be green.
3. Make tests hermetic by clearing all OpenAI-key aliases in provider-isolation fixtures; local developer credentials must never change expected test behavior.
4. Freeze one final commit, run three consecutive asserted proofs from that exact clean commit, and regenerate the screenshots after all UI changes.
5. Copy a sanitized final bundle into a tracked `examples/proof-run/` directory. Include the manifest, gates, workspace, receipt, recovery, timeline, screenshots, and a short explainer. Keep credentials and machine-specific paths out.
6. Replace the hardcoded `DataHub live` badge with a real health/context state: `connected`, `captured at`, `stale`, or `unavailable`.
7. Add a current architecture PNG/SVG and DataHub-specific 90–150 second demo script. Record one uninterrupted product workflow and publish the required public video.
8. Make `/proof` or a dedicated exchange page the repository's primary link. Remove old Prava, meeting-intelligence, Snowflake, and generic catalogue/checkout marketplace material from the judge path.
9. Put the pre-existing-code disclosure and hackathon-built file summary near the top of the README and in the submission description.
10. Provide a hosted read-only replay or a fully containerized one-command path. A judge should be able to inspect the proof without Windows or an 8 GB mutable environment.
11. Put the application commit and proof run ID visibly in every screenshot. Generate a signed screenshot index bound to the release manifest; filesystem timestamps alone do not prove screenshot provenance.
12. Add a release check that fails when `manifest.applicationCommit != HEAD`, the screenshot index is not bound to that manifest, required example files are untracked, or the working tree is dirty.

### P1 — turn the harness into one real cross-company exchange transaction

1. Add a buyer-created campaign: desired job, target DataHub asset, environment, budget/terms, candidate category, no-buy baseline, and requested effect.
2. Use MCP `search` and configurable lineage traversal instead of fixed URNs. Fail closed when ownership, schema, policy, or sensitivity is ambiguous.
3. Compile gates from sensitivity tags, structured properties, domains, glossary terms, data contracts, assertions/incidents, lifecycle, and multi-hop lineage.
4. Produce both a buyer-private manifest and a seller-safe challenge. Show every disclosed requirement with its exact DataHub cause and prove that private topology/raw data does not cross the boundary.
5. Add a SEIL conformance CLI and `proof-adapter.yaml` contract. A seller publishes identity, exact digest, protocol, capabilities, limitations, region, canary contract, price/SLA, evidence, expiry, and signature.
6. Run at least two separately identified seller services with separate persisted publications and keys. Consume their actual signed responses; remove `_published_projection` from the live path.
7. Send both sellers the same versioned challenge and hidden canary. The coordinator must not fabricate either offer inside the buyer process.
8. Clear a winner or explicit `NO_BUY` using deterministic eligibility plus declared commercial rules.
9. Add a pending authority state. Resolve all affected DataHub owners and procurement authority, authenticate the actors, allow inspect/approve/reject, and enforce requester/evaluator/approver separation.
10. Gate one exact procurement, provisioning, or deployment effect with the winning receipt. The existing local compare-and-set route is acceptable if described honestly.
11. Wire the live run through `ProofExchangeRepository` and `persist_proof_evidence`. PostgreSQL becomes canonical; evidence bundles become exports.
12. Replace process-local runner state with durable jobs, stage progress, cancellation, timeout, retries, logs, and reconciliation. Stop discarding stdout/stderr.
13. Show B/A/B as three inspectable snapshots, including the exact gate added or removed and each seller consequence. Today the UI mostly states the causal result.
14. Make multi-vendor comparability mandatory for the headline product and demo. Single-release pass/fail remains a useful module, not the positioning.
15. Establish an explicit untrusted-adapter threat model before accepting external seller images. Separate adapter and router socket volumes or put a narrow authenticated broker between them; use distinct UIDs, resource limits, `no-new-privileges`, seccomp/AppArmor, signed images, and SBOM/provenance verification.
16. Replace substring-based receipt verification with exact read-by-URN, canonical projection parsing, projection-hash recomputation, and equality checks.
17. Inject failure at the real MCP save boundary and prove exception-triggered rollback plus durable reconciliation; the existing pre-write branch is not a DataHub write failure.

### P2 — make the buyer and seller agents real without weakening safety

Add bounded agent layers that:

1. let SIRA interpret natural-language campaign intent, search DataHub, resolve the intended asset, and propose a typed campaign plan;
2. let SIRA identify missing or conflicting buyer context and route it to the correct owner;
3. let SEIL inspect the seller-safe challenge, select a conformant published release, and return a signed typed offer;
4. let either agent negotiate only missing typed evidence or unsupported requirements, never rewrite a failed gate;
5. invoke the deterministic compiler, trial runner, and clearing engine;
6. pause for authenticated human authority;
7. execute only the exact approved effect contract;
8. verify, write back, distribute filtered receipts, or compensate;
9. expose an auditable tool trace without presenting hidden reasoning.

Use Agent Context Kit or DataHub Skills for buyer-side graph exploration if they materially help. DataHub Agents may host SIRA. Do not let any LLM decide eligibility, fabricate context, approve its own effect, change commercial inputs after trials, or bypass the digest-bound kernel.

### P3 — create the compounding proof-exchange network

1. Subscribe to DataHub metadata changes and seller release events; mark only affected receipts stale.
2. Compute blast radius from receipt dependencies to active tools, campaigns, buyers, and seller releases.
3. Automatically rerun read-only trials; request fresh authority only if the cleared outcome or intended effect changes.
4. Register SIRA and tested releases in Agent Registry or Service Catalog, including owner, tools, model/runtime, version, and consumed datasets.
5. Write structured proof status, evaluation-contract hash, policy version, tested digest, expiry, and receipt relation to the relevant agent/service/release—not only a generic Document.
6. Preserve aspect/system-metadata versions or point-in-time references so historical proof is actually replayable.
7. Return a separately filtered, signed acknowledgment to each seller without exposing losing offers or the buyer's private graph.
8. Record incidents and post-deployment outcomes back to DataHub and use them in future campaigns.
9. Reuse a valid proof only when graph dependencies, policy, environment class, trial protocol, and artifact digest all match; show why reuse is valid.
10. Accumulate category-level conformance and outcome evidence without leaking buyer secrets or creating pay-to-win ranking.
11. Add realistic gates: PII, residency, schema compatibility, downstream blast radius, quality, latency, cost, tool permissions, and retention.
12. Support more than one procurement/deployment adapter behind the same verified-effect contract without becoming a generic orchestration platform.

### P4 — prove two-sided demand and usefulness

1. Interview at least five Data/AI Platform, security, governance, and technical-procurement practitioners who have run third-party tool evaluations.
2. Interview at least five vendor release/solutions engineers who repeat buyer-specific PoCs and security evidence work.
3. Capture the last real evaluation on both sides: systems touched, elapsed steps, artifacts, disclosures, approvals, rework, and what became stale.
4. Obtain one buyer design partner willing to supply a sanitized DataHub graph and two real tools or seller teams willing to publish SEIL offers.
5. Measure campaign setup time, seller response effort, time to comparable proof, unsafe-candidate catch rate, false blocks, approval latency, and requalification reuse.
6. Test willingness to participate in and pay for a verified campaign. Do not infer a marketplace from willingness to try a free gate.
7. Keep governed AI/data software as the first category. Generic B2B procurement is an expansion hypothesis.

### P5 — earn the open-source bonus meaningfully

Best options, in order:

1. Add a maintained OpenAI Agents SDK integration for Agent Context Kit/Agent Registry, with SIRA as a reference implementation, after confirming the upstream gap.
2. Contribute an exact `get_document` MCP tool with canonical content, version/system metadata, and tests; the current proof uses `grep_documents` for read-after-write verification.
3. Propose point-in-time/entity-version MCP reads for replayable receipts.
4. Contribute a context-bound external-action DataHub Skill: freeze graph dependencies, request authenticated approval, execute an allowlisted action, verify, and write back or compensate.
5. Publish a proof-adapter Service Catalog connector or reference that ingests tool/version/owner/artifact metadata and links it to consumed datasets.

Coordinate upstream first. A cosmetic documentation typo or project-specific tag is not a meaningful contribution.

## Milestone plan

### K6 — submission truth

Acceptance criteria:

- Public default branch equals the submitted commit.
- Full CI is green.
- 3/3 release evidence, screenshots, and video all come from that commit.
- Sanitized examples are tracked and machine paths removed.
- README, homepage, Devpost copy, and video tell the same executable proof-exchange story.
- Current limitations explicitly say synthetic graph, seeded actor, fixed local sellers, local effect, and no real purchase.

### K7 — first real multi-vendor exchange campaign

Acceptance criteria:

- A platform engineer can select a DataHub asset and open a campaign with a desired job, budget/terms, and no-buy baseline.
- SIRA discovers relevant context dynamically, shows its source, and compiles separate buyer-private and seller-safe artifacts.
- Two independently running SEIL seller services publish signed exact-release offers through the real conformance path.
- Both sellers receive the same challenge and hidden canary; no in-process fabricated projection is used.
- PostgreSQL stores campaign, challenge, signed offers, manifest, trials, clearing decision, and status transitions.
- The result is not structurally fixed to hardcoded candidates or prices.
- One seller release is a real open-source AI/data tool rather than a toy response fixture.
- Untrusted adapters cannot access sibling or router IPC and are constrained by an explicit runtime security policy.

### K8 — real transaction authority and effect

Acceptance criteria:

- The current DataHub owner and procurement/deployment authority receive a pending result and explicitly approve or reject it.
- Wrong owner, changed owner, stale context, changed digest, expiry, revocation, and self-approval all block.
- One exact conditional award, provisioning action, or deployment target changes; health/behavior are verified and recovery is durable.
- Receipt and effect state are read from canonical records, not the latest JSON file, and exact DataHub projection equality is verified.
- Buyer and seller receive different signed receipt views according to an explicit disclosure policy.

### K9 — bounded buyer and seller campaign agents

Acceptance criteria:

- A natural-language buyer request becomes a typed campaign scope through dynamic DataHub search and lineage exploration.
- Ambiguous or missing graph context causes a bounded clarification or safe stop.
- SIRA proposes a typed plan; each SEIL selects only a published conformant release and returns a signed typed offer.
- Agents can request missing typed evidence but cannot alter failed gates, clear the winner, or approve their own effect.
- The UI exposes buyer goal, graph sources, seller offers, plan, tool actions, authority state, verification, and compensation as an auditable trace.
- A replay test proves the same accepted context produces the same manifest and decision.

### K10 — continuous exchange and requalification

Acceptance criteria:

- A DataHub dependency change marks the correct proofs stale.
- A seller digest, evidence, price/SLA, suspension, or revocation change marks the correct offers and receipts stale.
- Blast radius identifies affected buyers, campaigns, effects, and releases.
- Safe read-only requalification runs automatically.
- A changed clearing result requests fresh authority; an unchanged result records scoped reusable evidence.
- DataHub contains structured, linked, queryable proof status.
- A seller receives a filtered requalification result without learning the buyer's private graph or competitors' offers.

### K11 — external proof and contribution

Acceptance criteria:

- Two real AI/data tools and one sanitized non-project DataHub graph pass through one multi-vendor campaign.
- A 2-by-2 interoperability test proves two buyer context profiles can evaluate the same two seller releases without buyer-specific or seller-specific code changes.
- At least three buyer-side and three seller-side practitioners complete their part of the journey and give structured feedback.
- One high-quality upstream DataHub contribution is opened with tests and maintainers' alignment.
- The demo can be understood and tried without project-author assistance.

## Demo story

Tell one uninterrupted three-minute market transaction:

1. **0:00–0:20, establish the market.** Maya, an AI platform engineer, opens a campaign for an EU support-summary capability. Show one buyer, two independently identified sellers, and `NO_BUY`.
2. **0:20–0:45, DataHub creates the challenge.** Maya selects the governed asset. SIRA reads schema, multi-hop lineage, email PII, EU policy, contracts/assertions, and owners. Show the buyer-private manifest beside the minimum-disclosure seller challenge.
3. **0:45–1:15, sellers respond.** Two separate SEIL endpoints return signed offers binding seller identity, exact image digest, capability/limitation, price/SLA, evidence, and expiry. No in-process fabricated projections.
4. **1:15–1:45, the exchange clears.** Both exact releases run the same hidden canary. The cheaper clear-text release fails the PII-derived gate; the redacting release wins. Show the exact DataHub facts that caused the result.
5. **1:45–2:10, authority becomes action.** The real DataHub owner approves the exact winning digest and effect. Activate it, send routed traffic, verify the digest, and exactly reread the canonical receipt projection from DataHub.
6. **2:10–2:35, prove buyer-side causality.** Change only the PII fact. With the same seller offers and releases, the cheaper candidate wins; restoring PII restores the original winner. An unrelated mutation changes nothing.
7. **2:35–2:50, prove seller-side invalidation.** The winning seller publishes a new digest. The old receipt cannot authorize it, so the exchange blocks until requalified.
8. **2:50–3:00, close on the network.** Show: `buyer graph -> private challenge -> signed offers -> equal trials -> winner/no-buy -> exact authority -> verified effect -> receipt -> two-sided invalidation`.

### What must be real in the final demo

- A user-created campaign rather than fixed constants.
- Live DataHub MCP reads, causal mutation, and writeback.
- A visible buyer-private to seller-safe disclosure boundary.
- Two separately running seller services with separate identities, keys, and persisted publications.
- Signed offers bound to exact artifact digests.
- Identical isolated trials and deterministic clearing, including `NO_BUY`.
- A visible owner approval action bound to the exact subject.
- Compare-and-set activation, routed behavior verification, and rollback.
- Exact receipt retrieval, canonical parsing, hash recomputation, and equality rather than substring search.
- Invalidation from both a relevant DataHub change and a seller digest change.
- Tracked, reproducible evidence from the submitted commit.

### What may remain simulated if labelled

- Buyer data, vendor companies, prices, legal terms, and hidden canaries.
- Corporate SSO; seeded demo identities are acceptable if the click/decision is real.
- The deployment target; the local router is acceptable.
- Payment, contract signature, and an actual purchase order.
- Internet-scale receipt portability and an existing liquid seller network.
- Hostile seller-code isolation; until the socket boundary is hardened, call the images trusted reference releases.

For the current build, do not fake the buyer campaign, dynamic discovery, independent sellers, human authority, seller-side invalidation, exact receipt equality, or structured Agent/Service writeback. Those are not implemented today. The honest current demo can show the live DataHub PII mutation, trial consequence, bounded route effect, fresh-session core-hash lookup, and rollback. The hashes support the story; they are not the story.

## Do not build next

- A one-line DataHub Agent wrapper as the headline product.
- Single-release admission as the company positioning.
- Another generic chat interface.
- A generic catalogue/search/checkout marketplace before the proof exchange works.
- Payments and licensing before one receipt gates a real procurement/provision/deployment action.
- Analytics Agent merely to add another DataHub logo.
- More hardcoded candidates or more synthetic hashes without a user action.
- A second decision engine or orchestration platform.
- Cosmetic DataHub writeback that future agents cannot query or reuse.
- Ten deployment connectors before one real end-to-end target works.

## Final definition of “there”

The project is there when a judge can clone the exact public commit or open a hosted replay, create a buyer campaign from a governed DataHub asset, watch at least two independent SEIL sellers submit exact releases, see equivalent trials clear a winner or no-buy, see real authority gate a real bounded action, inspect a portable receipt written to DataHub, change either a buyer dependency or seller digest and force the correct requalification, and reproduce the evidence with green CI.

Today, only the middle technical kernel is there. It is the right kernel for the exchange. The next work is not a larger DataHub agent; it is the first real bilateral transaction around that kernel.
