# Devpost submission copy

Live project: <https://devpost.com/software/sira-seil>

## Title

SIRA + SEIL: DataHub-Grounded Software Buying

## Tagline

Buy software that fits the company you actually run—not the company vendors imagine.

## Description

### The problem

Software buying starts with feature lists, sales calls, and generic demos. The real fit problems appear weeks later: a product cannot handle governed data, work in the required region, or fit the systems already in place.

SIRA + SEIL brings that truth into the decision before a company commits to a vendor or a long proof of concept.

### What it does

**SIRA works for the buyer.** It learns what the company needs and which products fit.

**SEIL works for sellers.** It turns product details, limitations, integrations, and evidence into listings that SIRA can compare.

For data and AI purchases, SIRA uses DataHub to understand the buyer's actual environment: what data exists, where it flows, who owns it, and what rules apply.

### The demo

A company needs a customer-support AI. The cheaper option looks better on price.

But DataHub shows that customer email is governed PII and must stay within an allowed region. Private Relay handles that correctly. ClearText Assist exposes the synthetic email, so SIRA blocks it and recommends Private Relay.

We then remove only the PII classification. The recommendation changes to ClearText Assist. An unrelated metadata change does nothing. Restoring the PII classification restores the original recommendation.

That proves DataHub changed the buying decision; it was not just another connector shown in the UI.

SIRA saves the decision back to DataHub so the company can reuse the reasoning during security review, procurement, or renewal.

### Why this matters

A bad software choice costs more than the licence. Teams lose weeks evaluating the wrong products, repeat the same diligence, and discover integration problems after they have already invested.

SIRA helps teams reject bad-fit options early and focus each evaluation on the risks that matter to their company.

### How it works

DataHub Core and the DataHub MCP Server provide the buyer context. SEIL provides comparable seller evidence. SIRA applies the same trial and eligibility checks to every candidate, tests whether the decisive DataHub fact really changes the result, restores the original state, and records the outcome.

The DataHub reads, changes, restoration, evaluation, and writeback are real. The demo company, products, prices, and data are synthetic.

### What's next

Use buyer-selected DataHub assets and evidence from real vendors to create a shortlist and a company-specific proof plan before purchase.

## Links

1. <https://seil-sira.vercel.app> — primary deployment target
2. <https://sira-seil.vercel.app> — fallback deployment
3. <https://github.com/sandip-pathe/sira-seil-datahub> — Apache-2.0 source
4. <https://vimeo.com/1217082462> — public 2:25 demo
