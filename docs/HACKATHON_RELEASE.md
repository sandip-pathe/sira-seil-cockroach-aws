# DataHub implementation and release notes

This is the technical appendix for the SIRA + SEIL DataHub demo. The product story and setup are in the [main README](../README.md).

## Decision path

1. The seed script publishes a synthetic buyer graph to self-hosted DataHub Core: datasets, schema fields, upstream lineage, ownership, a PII tag, and an allowed-region property.
2. The open-source DataHub MCP Server reads the graph twice. The proof proceeds only when both semantic reads match.
3. The context compiler converts DataHub metadata into schema, region, and conditional privacy requirements.
4. SEIL supplies two repository-curated, buyer-safe seller evidence projections. Seller-private fields are excluded.
5. Both candidates receive the same requirement IDs and synthetic trial case in network-disabled, read-only containers.
6. The deterministic Decision Graph applies eligibility gates before price.
7. The causal test removes the PII tag, checks that the recommendation changes, makes an unrelated metadata change as a negative control, and restores the PII tag and original decision.
8. A hash-bound projection of the restored decision is saved as a DataHub Decision document and verified through a new MCP session.
9. The API rejects incomplete evidence, mismatched hashes, failed restoration, or a missing reread before exposing the cited result in SIRA.

## Implementation map

| Responsibility | Code |
|---|---|
| Seed synthetic DataHub metadata | [`scripts/datahub_k0_seed.py`](../scripts/datahub_k0_seed.py) |
| MCP process, reads, mutations, and document reread | [`python/proof/datahub_mcp.py`](../python/proof/datahub_mcp.py) |
| Compile DataHub facts into requirements | [`python/proof/manifest_v0.py`](../python/proof/manifest_v0.py) |
| Create buyer-safe SEIL projections | [`python/proof/exchange.py`](../python/proof/exchange.py) |
| Run the counterfactual and negative control | [`python/proof/causal_demo.py`](../python/proof/causal_demo.py) |
| Bind the decision projection and DataHub reread | [`python/proof/exchange_demo.py`](../python/proof/exchange_demo.py) |
| Apply deterministic selection | [`python/proof/decision_bridge.py`](../python/proof/decision_bridge.py) |
| Run isolated candidate trials | [`infra/datahub/k0/runtime/campaign_probe.py`](../infra/datahub/k0/runtime/campaign_probe.py) |
| Reject invalid artifacts at the API boundary | [`services/api/sira_api/proof_runtime.py`](../services/api/sira_api/proof_runtime.py) |
| Compose the cited SIRA inspector view | [`services/api/sira_api/workspace_service.py`](../services/api/sira_api/workspace_service.py) |

## Trust boundary

DataHub answers what the buyer's environment contains, depends on, and permits. SEIL supplies normalized seller evidence. SIRA decides which product fits and what still needs proof.

Candidate adapters receive only requirement IDs, allowed regions, and synthetic inputs. They never receive dataset rows, DataHub credentials, asset URNs, ownership records, or the buyer's dependency graph.

The proof uses upstream dataset lineage as source context. It does not claim that column-level lineage drives the decision. DataHub stores a hash-bound decision projection, not the full internal receipt or an immutable ledger.

## Reproduce the asserted proof

From a clean checkout on Windows:

```powershell
corepack pnpm install --frozen-lockfile
uv sync --all-extras --frozen
.\scripts\proof.cmd up
.\scripts\proof.cmd doctor -Contract
.\scripts\proof.cmd demo -Assert -Artifacts .artifacts/proof
```

For a three-run release check:

```powershell
.\scripts\proof.cmd demo -Assert -Artifacts .artifacts/release/run-1
.\scripts\proof.cmd demo -Assert -Artifacts .artifacts/release/run-2
.\scripts\proof.cmd demo -Assert -Artifacts .artifacts/release/run-3
.\.venv\Scripts\python.exe scripts\verify_release_runs.py `
  --runs .artifacts/release/run-1 .artifacts/release/run-2 .artifacts/release/run-3 `
  --output .artifacts/submission
```

Run the API on the Windows host for this demo because the proof bridge invokes `scripts/proof.ps1`; the containerized API image intentionally omits PowerShell.

## Recovery

1. Run `.\scripts\proof.cmd reset`.
2. Run `.\scripts\proof.cmd doctor -Contract`.
3. Confirm the PII tag is present and the unrelated control tag is absent.
4. Rerun the asserted demo and confirm the restored decision hash matches the baseline.
5. Confirm the DataHub document reread matched the expected decision and evidence hashes.
6. If DataHub is unhealthy, run `down`, then `up`, then `reset` before retrying.

Never reuse a previous recommendation after a partial run. The API is designed to fail closed.

## Claim boundary

Real local operations: DataHub reads, metadata changes, restoration, isolated trials, deterministic comparison, document writeback, and fresh reread.

Synthetic: company, graph contents, candidates, prices, trial inputs, and the two repository-curated seller projections. The demo proves a buyer-specific technical-fit decision; it does not represent a live vendor marketplace, a completed purchase, or arbitrary production deployment.

The repository pins `mcp-server-datahub` 0.6.0 and explicitly enables its mutation tools with `TOOLS_IS_MUTATION_ENABLED=true`. Local DataHub credentials remain in the user's standard profile and are never bundled.

## DataHub references

- [MCP Server](https://docs.datahub.com/docs/features/feature-guides/mcp)
- [Lineage](https://docs.datahub.com/docs/features/feature-guides/lineage)
- [Structured Properties](https://docs.datahub.com/docs/features/feature-guides/properties/overview)
- [Tags API](https://docs.datahub.com/docs/api/tutorials/tags)
- [Ownership API](https://docs.datahub.com/docs/api/tutorials/owners)
- [Documents API](https://docs.datahub.com/docs/api/tutorials/documents)
