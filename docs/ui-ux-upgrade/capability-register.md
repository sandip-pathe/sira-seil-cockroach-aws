# Capability register (baseline)

Audit date: 2026-10-21. “Source implemented” means a repository path and server contract exist. “Locally verified” refers to the previously run repository test/build suite; it does not mean a live provider account or production deployment was verified.

| Capability shown or implied | UI / route | Server contract and durable state | Policy / readiness / environment |
| --- | --- | --- | --- |
| SIRA buyer workspace, decision brief and candidate comparison | `/sira`; `CommerceWorkspace` | Purchase-request, discovery, decision-view and brief APIs; decision/artifact records in CockroachDB | Source implemented; deterministic trust-boundary evaluator is 5/5, zero provider calls. Live OpenAI quality/provider account is unverified. |
| Public product research and catalog search | SIRA workspace; workspace catalog/search controls | `POST /v1/marketplace/research`, catalog GET routes; persisted product and versioned observation records | Source implemented and repo checks passed. Provider source membership is checked; assertion truth is not independently verified. Live provider call not run for this audit. |
| SEIL product draft and evidence editing | `/seil`, `/seil/products/search`, `/seil/product-evidence/[productId]` | Seller product/evidence APIs, tenant-owned drafts and versions | Source implemented. Real seller login depends on Firebase configuration. |
| Seller review, publication and withdrawal | SEIL product evidence surface | Review/publication APIs; allowlisted public projection and catalog observation transaction; withdrawal timestamp | Server authority and durable state implemented; covered by repository checks. No production tenant verification. |
| Buyer/seller consent and qualified introduction | SIRA inbox/decision and exchange UI | Qualification service consent/introduction commands; durable consent and introduction records | Source implemented; actor/permission checks server-side. No customer journey observation. |
| Seller exchange and offer negotiation | `/exchange/[caseId]` | Exchange case, message/offer records and exact offer state | Source implemented; role/organization authorization required. External counterpart integration is not implied. |
| Spend approval and purchase intent lock | SIRA decision/action UI and API | `/v1/purchase-intents`, approval requests, exact purchase intent | Contract and step-up permission routes exist. No UI-path/tenant-level end-to-end verification in this audit. |
| Payment handoff | Purchase intent action; exchange context | `/v1/purchase-intents/{id}/payment-handoff`, `/v1/payment-handoffs/{id}/open`; exact amount/currency/recipient/reference and expiry | Human-operated external HTTPS handoff only. No card/token handling, charge result, refund, or entitlement authority. Production merchant/provider setup not verified. |
| Company business context | Workspace Connectors panel | Context API and persisted typed context items; UI can request setup | Manual context is supported. API connector list exposes Business Context “Needs setup”. Imported suite data is not available. |
| Google Workspace | Connectors panel | Connector list reports “Not connected”; no OAuth/sync capability demonstrated by the inspected workspace route | UI discovery/status only; integration unavailable/unverified. |
| Microsoft 365, Slack, Teams, Zoom | Landing/workspace marketing or connector copy | No corresponding connector listed by `workspace_routes.py`; no verified lifecycle/API found in this audit | Do not present as available integrations; claim gap tracked for Step 12. |
| Hosted checkout / vendor fulfillment | Connector copy and commercial language | Human handoff routes only; no verified payment provider completion or fulfillment callback | Not implemented/verified as automated execution. User and seller complete outside the platform. |
| MCPs, skills, internal tools, API key provisioning, office-suite administration | Category ambitions in playbook/marketing | No product-specific capability contract or verified tool execution path found in audited surface | Research/preparation only; out of current executable scope. |

## Evidence and confidence labels

- **Fixture/demo:** workspace includes demo product/message examples; fixture content must not be confused with live catalog truth.
- **Source implemented:** route/service/domain behavior exists and normal automated checks passed during release validation.
- **Locally verified:** broad automated checks passed; migration chain was applied to a fresh local Cockroach database. Live integration paths were excluded.
- **Deployed/verified:** none established by this audit.

This register is a source audit, not a complete route-by-route interactive verification. Recheck the `ConnectorsPanel` copy and landing claims against `workspace_routes.py` before release-scope decisions.
