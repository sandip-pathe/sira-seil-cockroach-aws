# Source provenance

SIRA and SEIL predate the CockroachDB x AWS hackathon. The repository preserves their original Git history rather than presenting the reused product as a new initial commit.

Original source history:

- upstream: `uruja/siel-n-sira`
- imported branch: `core-backend`
- imported commit: `8d917eba039b59b2c1a0f35d832093806101260c`
- original development began during the prior hackathon window in August 2026

New work for the current hackathon begins at the `cockroachdb-hackathon-start` tag. It includes only the CockroachDB state layer, distributed vector retrieval, concurrency and recovery behavior, Cloud MCP inspection, Bedrock integration, and AWS deployment that are actually implemented and verified after that boundary.

Previous sponsor-specific integrations are available in Git history but are not part of the active product or current submission.

All repository fixtures describe synthetic companies, products, prices, and test inputs. Third-party services retain their own licenses. Project-authored code is Apache-2.0 licensed.
