# Open decisions and external checks

These do not change the product direction.

## Before cloud deployment

- [ ] Choose the CockroachDB Cloud region and plan after verifying vector-index availability.
- [ ] Create separate migration, runtime, and read-only MCP identities.
- [ ] Verify the final RLS/session-scope pattern against every critical write path.
- [ ] Benchmark the tenant-prefixed context and public-catalog vector queries.
- [ ] Verify Bedrock Titan Text Embeddings V2 access using the ECS task role in the chosen AWS region.
- [ ] Decide whether the public frontend remains on Vercel or moves to AWS; API and workers remain on AWS.
- [ ] Lock the synthetic corpus size and retrieval relevance labels.
- [ ] Lock the safe demo-control contract: explicit synthetic tenant, scenario, one-time run ID, database control record, and no browser AWS control-plane permission.

## Existing non-migration debt

- [ ] Correct the pre-existing deterministic decision fixture/ranking drift and preserve an explicit baseline.
- [ ] Re-run a current-tree credential scan separately from historical inert test literals.

## Only after the hosted proof passes

- [ ] Decide whether a changefeed plus idempotent Lambda adds enough value.
- [ ] Search the CockroachDB Agent Skills repository before proposing a narrow skill.
- [ ] Consider measured multi-region or live discovery work only if it cannot weaken submission evidence.
