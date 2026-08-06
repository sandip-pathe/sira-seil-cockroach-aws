# Snowflake apply order

Run these files against the same account configured as `SNOWFLAKE_ACCOUNT`:

1. `00_preflight.sql`
2. `01_bootstrap.sql`
3. `02_governed_tables.sql`
4. `03_evidence_pipeline.sql`
5. Upload the two files under `fixtures/snowflake/seller_evidence/` to the paths
   documented in `08_ingest_seller_evidence.sql`.
6. `08_ingest_seller_evidence.sql`
7. `04_cortex_search.sql`
8. `05_decision_ledger.sql`
9. Run `06_code_stage.sql`, build/upload the bundle with
   `scripts/build_snowflake_bundle.ps1`, then run `06_snowpark_evaluator.sql`.
10. `07_seed_demo.sql`
11. `10_runtime_identity.sql` when creating the least-privilege runtime identity.
12. `worksheets/causal_proof.sql`

Files are rerunnable. The ledger script contains forward migrations for deployments
created before organization-scoped requests and approvals. The ingest script derives
decisive chunk text and hashes directly from persisted `AI_PARSE_DOCUMENT` output.

Do not deploy the API until the configured app user can select `organization_id`
from `DECISION.REQUESTS` and the three scoped columns (`organization_id`,
`request_id`, `run_id`) from `DECISION.APPROVAL_LEDGER`.
