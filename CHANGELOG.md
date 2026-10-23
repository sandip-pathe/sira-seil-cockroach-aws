# Changelog

## [0.2.0.0] - 2026-10-21

### Added

- Search and compare a persistent B2B product catalog with source-linked public research, freshness indicators, and a clear distinction between researched and seller-published evidence.
- Let sellers register products privately, publish evidence after review, and withdraw listings when a published pack is suspended.
- Add the SIRA + SEIL synthesis-driven design playbook, implementation plan, and supporting flow, human-control, integration, and copy specifications.
- Run qualification work through an OpenAI-backed Python runtime and durable outbox worker.

### Changed

- Route product research, model access, embeddings, and worker configuration through server-side OpenAI settings.
- Extend marketplace, seller, workspace, and API-client contracts to support persistent product evidence and product registration.
- Document the current product architecture, operating setup, and marketplace behavior.

### Removed

- Retire the AWS Bedrock and AgentCore deployment, runtime services, scripts, and CI jobs.
- Remove the unused external-runtime replay-ticket table and its associated code.
