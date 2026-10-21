# Step 00 research findings and decision episodes

Audit date: 2026-10-21.

## Research actually available

- Repository routes, components, API contracts, domain models, evaluator fixtures, and current product/architecture documentation were inspected.
- The reference adaptation documented in `docs/product-marketplace.md` describes Jack and Jill's public-facing hiring pattern: one agent works with candidates and one with hiring teams through a brief and evaluation gates. The product adopts the two-sided workflow pattern; no claim is made about Jack and Jill internals.
- The repository's five-query retrieval fixture concerns meeting software: Granola, Fathom, tl;dv, Fireflies, and a generic decoy. It covers shared notes, conferencing compatibility, EU hosting, CRM sync, and retention evidence.
- The deterministic qualification report has five trust-boundary cases (5/5 pass, 0 provider calls). It tests grounding enforcement, not live model quality or buyer comprehension.

## Evidence not available

No customer interview recordings/transcripts, observed work sessions, support-ticket corpus, analytics event export, seller response sample, or production deployment evidence was available in the repository/session. Therefore this document makes no customer-quote, frequency, conversion, time-saving, comprehension, seller-usefulness, or production adoption claim. Observed user episodes: **0**. Production event sample: **0**. These are availability counts for this audit, not claims that no such data exists elsewhere.

## Repository-derived friction hypotheses (not research findings)

1. Entry aliases `/inbox` and `/settings/profile` lead to public `/`, while role-specific destinations exist; this may break expected task continuity for inbound links.
2. Buyer decision deep links encode current decision version and stage in the query string; unauthorized, stale or missing records need explicit recovery and preservation behavior.
3. Connector UI examples appear broader than server capability. A user may mistake an illustrative or unimplemented integration for an available one.
4. Demo agent messages use confident results and counts. Without visible demo/currentness labels, users can interpret fixture content as live marketplace evidence.
5. The path from public research to a seller-owned, reviewed and published record crosses distinct ownership and authority boundaries. The interface needs to show that research is not seller verification or a purchase recommendation.
6. Payment handoff and purchase-outcome checkpoints are separate. A link opening cannot be presented as a completed purchase or fulfillment.

## Mechanisms to carry into Step 03

- Preserve the two-agent/two-sided pattern, but make each agent's audience, owned artifact and authority explicit.
- Use progressive, explicit gates: need/brief → evidence-backed options → selected next action → approval/consent → external handoff → reported or verified outcome.
- Put source, observation time, owner, confidence and missing evidence beside a claim; never rely on prose alone for authority.
- Carry task state, query, selected record, version and return path through auth, errors and redirects where authorized.
- Keep human review and disclosure preview adjacent to irreversible external release/publication.

Customer workarounds and episode harvesting remain a dependency for prioritizing friction hypotheses; collect before claims about user impact or before Step 14 optimization.
