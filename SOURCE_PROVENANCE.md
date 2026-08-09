# Source provenance

This repository began as a clean source snapshot of the SIRA + SEIL platform.

- Source repository: `https://github.com/uruja/siel-n-sira`
- Source branch: `core-backend`
- Source commit: `8d917eba039b59b2c1a0f35d832093806101260c`
- Source commit subject: `Merge Snowflake demo polish`
- Snapshot date: 2026-08-08

The previous hackathon repositories remain independent historical records. Their branch
history was intentionally not imported into this product-development repository.

## DataHub proof additions

The SIRA Proof of Fit implementation was developed in this repository after the snapshot.
It integrates, but does not vendor, DataHub Core 1.7.0, `acryl-datahub` 1.7.0, and
`mcp-server-datahub` 0.6.0. Those dependencies retain their own licenses. Proof adapters,
seed metadata, manifests, decision logic, router effects, receipts, release scripts, and
the operator workspace in this repository are project-authored. All demonstrated data is
synthetic.
