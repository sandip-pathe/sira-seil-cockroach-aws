# SIRA + SEIL product direction

Updated 10 August 2026.

## The product we are building

SIRA + SEIL helps enterprises choose, buy, replace, and renew software for the stack they actually run.

- **SIRA** is the buyer-side agent. It privately derives requirements from the buyer's environment, compares products, explains blockers, and produces a buyer-specific recommendation and proof plan.
- **SEIL** is the seller-side agent and evidence boundary. It supplies normalized, versioned product claims and release evidence without exposing seller-private material.
- **DataHub** is the deepest buyer-context layer for data and AI purchases. It supplies schemas, platforms, lineage, classifications, owners, policies, regions, and downstream dependencies.

The durable question is: **What should this company buy, replace, or renew for its actual environment?**

## Why DataHub matters

DataHub is not a decorative connector and it is not the whole product. It is the buyer's private technical truth.

SIRA turns DataHub metadata into concrete purchasing constraints, maps seller evidence to those constraints, and changes the recommendation when a decisive governed fact changes. The current reference flow proves this causally:

1. Customer email is classified as governed PII, so Private Relay wins.
2. Removing only that classification makes lower-priced ClearText Assist eligible and changes the winner.
3. Restoring the classification restores Private Relay as the winner.
4. An unrelated metadata mutation does not change the decision.
5. The decision receipt is written to DataHub and reread successfully.

Without DataHub, SIRA can still offer a generic software comparison, but it cannot make the buyer-specific technical decision. Without SIRA + SEIL, DataHub knows the internal estate but does not own cross-vendor sourcing, seller evidence, commercial comparison, procurement workflow, or the final buy/replace/renew decision.

## What we rejected

We rejected three directions as the primary product:

- A generic chatbot or recommendation wrapper. It is too easy to reproduce and lacks buyer-specific authority.
- A DataHub-native governance, lineage, metadata-cleaning, or catalog agent. DataHub can build those internally and they move us away from procurement.
- A full proof-to-production exchange as the immediate wedge. It has large theoretical value, but requires a vendor-adapter ecosystem, privileged activation access, standardized trials, and liability-heavy deployment controls before the buying product has earned adoption.

The standalone `/proof` surface was a symptom of the third mistake. Proof is now an internal decision primitive rendered inside the existing `/sira` conversation and inspector, not a separate product.

The older root-level `improve.md` records the earlier proof-exchange audit and remains useful historical context, but this document supersedes its product positioning.

## Current wedge

Start with consequential data and AI software decisions where internal metadata materially affects fit: customer-support AI, data platforms, observability, ML infrastructure, data processing, and tools that touch governed datasets.

The first complete product loop is:

`buyer request -> private DataHub context -> compiled requirements -> normalized SEIL evidence -> comparable options -> deterministic fit decision -> buyer-specific proof plan -> versioned decision receipt`

This is stronger than a small workflow because it combines private company context, external seller evidence, causal fit evaluation, and a reusable procurement decision record.

## Value thesis

This is a strong inferred value thesis, not validated willingness to pay yet.

The economic value comes from reducing evaluator labor and decision time, avoiding false-shortlist proofs of concept, catching integration or governance blockers before purchase, preventing failed migrations, and producing better evidence for negotiation. The most likely champion is a VP Data, CDO, Head of Data Platform, or AI Infrastructure leader; procurement benefits but is not the first champion.

What remains to validate:

- Will buyers grant metadata access for evaluations?
- Does DataHub context change real shortlists often enough?
- Will sellers provide normalized, release-specific evidence?
- Do target companies make enough consequential decisions each year to support an annual contract?
- Which budget owner will pay, and how much of the avoided labor and misfit risk can we capture?

## Current implemented milestone

The product now keeps the original SIRA workspace and adds a causal DataHub-grounded decision inside it:

- `/proof` and `/sira/proof` redirect to `/sira`.
- The starter mission compares two fictional customer-support AI products.
- The API reads the verified DataHub proof artifact and fails closed if its causal sequence, seller evidence, restoration, hashes, or receipt are invalid.
- The right inspector shows six exact DataHub facts and source URNs, three derived requirements, both candidates, the decisive counterfactual, the negative control, and the reread receipt.
- DataHub metadata changes the recommendation; unrelated metadata does not.
- The local live proof completes within the three-minute budget.

## Next product milestone

Replace the fictional candidates with a credible category evaluation while preserving the same contract:

1. Let the buyer choose a real data/AI software category and target workload.
2. Read the relevant DataHub assets dynamically rather than from fixed demo URNs.
3. Compile buyer-specific requirements and blockers from that context.
4. Ingest normalized evidence for two or three real products through SEIL.
5. Generate a buyer-specific proof-of-concept plan, not a production activation workflow.
6. Save the recommendation, evidence snapshot, assumptions, and expiry as the decision receipt.
7. Test demand with design partners and measure evaluation hours saved, shortlist changes, avoided proofs of concept, and willingness to pay.

The hackathon story and the commercial story are therefore aligned: **SIRA + SEIL helps companies buy software for the stack they actually run, and DataHub makes the data/AI recommendation company-specific, causal, and defensible.**
