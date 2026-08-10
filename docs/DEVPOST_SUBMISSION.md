# Devpost submission copy

Live project: <https://devpost.com/software/sira-seil>

## Title

SIRA + SEIL: DataHub-Grounded Software Buying

## Tagline

SIRA turns DataHub context into buyer requirements; SEIL supplies versioned vendor evidence; deterministic gates show which data and AI product actually fits.

## Description

### Inspiration

Data and AI teams often shortlist software from feature pages and generic demos. The expensive blockers appear later: a governed field cannot leave an allowed region, a required schema is unsupported, or a product conflicts with downstream dependencies.

Those facts already exist in DataHub. The missing layer connects the buyer's private technical context with comparable vendor evidence before a proof of concept begins.

### What it does

SIRA + SEIL helps enterprises choose, replace, and renew data and AI software for the stack they actually run.

- **SIRA** is the buyer agent. It reads the buyer's DataHub graph, derives hard requirements, compares candidates, and explains the decision.
- **SEIL** is the seller evidence agent. It turns reviewed product sources, constraints, integrations, and release evidence into versioned Product Evidence.
- **DataHub** supplies the buyer's schemas, lineage, classifications, ownership, regions, and dependencies.

In the demo, SIRA compares two fictional customer-support AI releases. DataHub shows that customer email is governed PII and that the relevant asset has an EU allowed-execution-region property. SIRA compiles those facts into three eligibility gates.

Private Relay passes all three. Lower-priced ClearText Assist returns the synthetic email unredacted and is blocked.

The proof then removes only the decisive PII classification. The winner changes to ClearText Assist. An unrelated metadata change leaves the decision unchanged. Restoring PII restores Private Relay and reproduces the original hashes.

Finally, SIRA writes a hash-bound decision receipt projection to a DataHub Decision document and verifies it through a fresh MCP session.

### Why DataHub is essential

Without DataHub, SIRA can produce only a generic product comparison. It cannot know what the buyer's estate contains, depends on, or permits.

Without SIRA + SEIL, DataHub does not compare external products or turn seller evidence into a buy, replace, or renew decision. This is procurement grounded by DataHub, not a catalog search or lineage viewer.

### How I built it

The project uses DataHub Core 1.7.0, the open-source DataHub MCP Server 0.6.0, Python, FastAPI, PostgreSQL, Docker, TypeScript, and Next.js.

`DataHub reads -> buyer requirements -> SEIL evidence -> equal trials -> deterministic decision -> counterfactual -> restoration -> DataHub writeback and reread`

The language model can explain the result, but deterministic gates own eligibility and selection. Both candidates receive the same synthetic trial. The buyer's raw DataHub graph never crosses the seller boundary.

### Challenges and lessons

The hard part was making DataHub causal rather than decorative. A relevant metadata change had to alter the recommendation for a clear reason, while an unrelated change had to leave it stable. The original metadata also had to be restored if any step failed.

A successful write response was not enough. The receipt projection is marked verified only after a new MCP session finds the expected core and projection hashes.

### What is real

The DataHub MCP reads, metadata mutation, restoration, trial execution, decision graph, negative control, writeback, and fresh reread are real.

The company, graph contents, product names, prices, trial inputs, and two repository-curated SEIL evidence projections are synthetic. No customer PII or purchase is involved.

The SIRA + SEIL workspace predates the hackathon. The DataHub MCP integration, causal procurement flow, proof runtime, counterfactual, writeback, and DataHub-grounded decision UI were built for this event.

### What's next

The next step is to evaluate real product categories using buyer-selected DataHub assets and source-backed, release-specific vendor evidence. SIRA will produce a buyer-specific shortlist and proof-of-concept plan before procurement begins.

## Links

1. <https://seil-sira.vercel.app> — primary deployment target
2. <https://sira-seil.vercel.app> — fallback deployment
3. <https://github.com/sandip-pathe/sira-seil-datahub> — Apache-2.0 source
4. <https://vimeo.com/1217082462> — public 2:25 demo
