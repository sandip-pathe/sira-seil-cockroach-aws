# SIRA Proof of Fit

SIRA is a buyer agent that does not trust a software claim until it can prove the release fits the buyer's governed environment. SEIL is the seller-side boundary that publishes a minimum-disclosure, executable proof adapter.

Together they turn internal software purchasing from “compare pages and book a demo” into a governed transaction:

`DataHub fact → requirement manifest → identical trials → deterministic winner → exact owner approval → verified effect → immutable receipt`

## Why DataHub is essential

DataHub is the live causal and authority plane, not a connector badge or citation source.

- SIRA reads schemas, lineage, tags, structured properties, and ownership through DataHub MCP.
- A real governed fact changes the executable requirements and flips the selected seller release.
- The current DataHub owner authorizes one exact manifest, decision, projection, and artifact digest.
- After real routed traffic verifies the selected digest, SIRA projects the historical receipt to DataHub and proves it by a fresh reread.

The demo holds every non-DataHub input fixed and produces `adapter B → adapter A → adapter B` by removing and restoring one PII tag. An unrelated governed mutation is the negative control and cannot change the decision.

## Run the proof

Requirements:

- Windows with PowerShell
- Docker Desktop with Compose
- Node.js 22+, pnpm 11, Python 3.12+, and `uv`
- About 8 GB of free memory for the local DataHub quickstart

No DataHub Cloud account or hackathon credential is required. The runner starts self-hosted DataHub Core 1.7.0, enables local authentication, and uses the open-source DataHub MCP server 0.6.0. Its local token stays in the standard DataHub profile outside this repository.

```powershell
.\scripts\proof.cmd up
.\scripts\proof.cmd doctor
.\scripts\proof.cmd demo -Assert -Artifacts .artifacts/proof
```

Start the product API and web app in a second terminal:

```powershell
docker compose up --build -d --wait api
corepack pnpm install --frozen-lockfile
corepack pnpm dev:web
```

Open the operator workspace at <http://localhost:3000/proof>. It shows the exact same context, trials, approval, active digest, receipt hash, DataHub reread, and restoration state as `.artifacts/proof/workspace.json`.

The public proof CLI is intentionally frozen to five verbs:

```powershell
.\scripts\proof.cmd doctor             # read-only health
.\scripts\proof.cmd up                 # start DataHub and isolated adapters
.\scripts\proof.cmd demo -Assert       # run and verify the transaction
.\scripts\proof.cmd reset              # restore the seeded PII tag and route
.\scripts\proof.cmd down               # stop proof services
```

## What the assertion proves

- Seller releases cross an allowlisted SEIL-to-SIRA projection boundary; private seller fields do not.
- Both immutable image digests receive the same synthetic inputs in network-isolated containers.
- The existing deterministic Decision Graph selects the eligible release.
- Wrong-owner, stale-context, substituted-digest, expired, and revoked approvals block before any router call.
- Tested = selected = approved = healthy = active digest.
- Activation uses compare-and-set, serves real routed traffic, and rolls back to the prior digest.
- The receipt core excludes timestamps, delivery state, and its own hash.
- DataHub writeback is successful only after a fresh MCP reread matches the receipt.
- An induced writeback failure issues no success receipt and verifies rollback.
- The final PII tag, control tag, and route match their original state.

All inputs and products are synthetic. The proof demonstrates a bounded local deployment mechanism, not arbitrary production deployment or a real software purchase.

## Product surfaces

- **Context** — live DataHub health, fingerprint, decisive fact, requirements, and provenance.
- **Proof run** — two SEIL releases, identical trials, gate results, artifacts, and deterministic winner.
- **Activation** — exact owner authority, digest identity, health, routed traffic, and rollback.
- **Receipt** — immutable core, DataHub projection/reread, counterfactual, and recovery evidence.

The API contract is generated from `contracts/openapi/openapi.json`; the typed client lives in `packages/api-client`. The proof routes are `/v1/proof/workspace`, `/v1/proof/runs/current`, and `/v1/proof/runs`.

## Repository verification

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check.ps1
pnpm build:web
```

PostgreSQL is the canonical durable store. Tenant-owned proof projections, exact approvals, effects, and receipt cores use forced row-level security. Receipt cores are insert-only. Provider credentials have no persistence column.
