# Step 01 business context, objects, and authority

Status: working product model, grounded in current contracts; commercial policy decisions remain open. Audit date: 2026-10-21.

This document uses jobs-to-be-done for role needs, a service blueprint for the buyer/seller exchange, a domain object map for durable artifacts, and least-authority/action-specific review for human control. Proposed experience defaults are not represented as already-enforced server policy.

## 1. Job cards

| Role / job | Trigger and desired progress | Workaround / success | Current responsibility and limit |
| --- | --- | --- | --- |
| Buyer requester | A team has a software need; produce a clear brief with constraints and known context | Usually reconcile docs, spreadsheets, vendor pages and stakeholder messages; success is a useful, reviewable brief and evidence-backed options | Can submit requests and view context under current buyer identity. A requester is not automatically the spend approver. |
| Buyer evaluator | Candidate options need fit, source and trade-off review | Manually compare vendor claims and current stack; success is explaining why each option fits or has a gap | Can view, select and provide feedback under current capability. Research is not approval or a verified vendor claim. |
| Buyer approver / budget owner | A specific commitment is proposed | Review exact terms, approval basis and authority; success is a durable decision scoped to current terms/version | Current Firebase buyer role grants approval/execution permissions only for a verified identity and step-up rules apply to protected actions. Distinct budget-owner membership/routing is not fully modeled by workspace mode. |
| Buyer policy / IT reviewer | A hard requirement, data boundary or exception needs review | Validate exact rule and affected decision; success is an attributable policy decision | Actor roles exist in the decision projection, but membership assignment and policy-owner workflow need business/tenant verification. |
| Procurement / finance operations | An approved purchase needs an external handoff and follow-up | Re-enter exact amount, recipient and reference into vendor flow; success is an attributed external outcome with no false completion | Purchase intent, approval and human-operated handoff contracts exist. Automated checkout, settlement and fulfillment are outside this contract. |
| Organization admin | Configure identity and company policy, control access and recover access issues | Coordinate account owner, identity admin and procurement policy manually | No verified in-product organization-member administration workflow was found in the audited routes. Do not label a workspace user “admin” based on URL or UI mode. |
| Seller editor | Product facts, plans or sources change | Maintain decks, web pages and repeated questionnaires; success is a private, source-linked draft with less repeated work | Authenticated seller editor can maintain drafts. Draft remains private until the workflow authorizes publication. |
| Seller reviewer / commercial owner | Seller evidence or terms are ready to release | Review claims, source dates, fit/anti-fit and exact commercial terms | Reviewer/actor authority is evaluated server-side in seller workflow. A sales contact is not implicitly allowed to publish or accept terms. |
| Returning user | An interrupted mission, evidence review or approval resumes | Search inbox/email/history and reconstruct decisions | Existing mission/inbox/deep-link surfaces should preserve artifact, current version, next owner and route. Cross-channel notification delivery is not verified. |

These are job definitions for the proposed design, not evidence that interviews confirmed their frequency or language. The current auth adapter maps workspace modes to broad actor capabilities; future UI must render server-projected capabilities and party identity rather than infer individual job roles from the selected workspace.

## 2. Value exchange and positioning boundary

**Buyer value:** reduce fragmented software research by turning a need and company context into an inspectable, source-linked decision and a governed next step.

**Seller value:** maintain reviewed, reusable product evidence and respond to a need when the evidence supports fit.

**Platform role:** organize a bilateral workflow, source and version evidence, enforce explicit release/consent/approval boundaries, and preserve the status of external handoff. The platform is not the seller of listed software, a guarantee of vendor claims, or the authority for an external contract's fulfillment.

**Qualification meaning:** eligibility/fit is based on declared criteria and attributable evidence. Seller payment or catalog presence does not change rank. A product found through public research is not thereby seller-verified, qualified, endorsed, or purchasable.

**Commercial default:** no platform fee, commission, take rate, pricing plan, savings guarantee, service level, or transaction guarantee is set by this product model. Publish only after a business owner approves specific terms. Exact vendor terms remain subject to confirmation with the vendor.

## 3. Durable objects and visibility map

| Object | Identity / owner / version | Visibility and state boundary | Current authority evidence |
| --- | --- | --- | --- |
| Company context item + version | Tenant item ID; current version ID/number/hash; actor and change reason | Buyer-private, active or retired; mission can bind selected version | `CompanyContextItem` / `CompanyContextVersion`; create/update/retire require buyer and `can_manage_procurement_gate`, human identity, idempotency and current ETag. |
| Qualification mission | Mission/request identity, buyer organization, selected context IDs, lifecycle | Buyer-private; source research may be public but the query/need is not a shared product field | Qualification service and durable mission/request records; access checked under buyer context. |
| Requirement brief version | Brief identity/version, category, goal, criteria, seller-visible projection | Draft/private until a release command creates an allowlisted release | Exchange release validates current brief, expiry, completeness and allowlist before state changes. |
| Marketplace product + observation | Canonical URL/edition identity; observation version, source links/hash/time/expiry | Public product facts only; no buyer private budget or query | Catalog records and source-bounded public web research; seller-owned published projection remains distinguishable. |
| Seller product/evidence pack | Seller tenant/product identity, evidence/source versions, reviewer and publication state | Private draft until approved publication; public projection allowlisted; withdrawal is effective state | Seller routes/services, evidence models, review/publish and suspend operations. |
| Qualification result / decision artifact | Request/version, evidence source IDs and criterion-specific result | Buyer-visible; does not grant disclosure or spend authority | Deterministic policy/qualification output and persisted decision artifacts; model output is validated before commit. |
| Engagement / consent | Buyer request + seller organization, purpose, participants, scope/version/expiry | Shared only to the parties and fields authorized by consent; pending/accepted/declined/expired/superseded | Qualification APIs require current human authority; introductions are created only after required consent. Exact projection must remain allowlisted. |
| Seller response / offer version | Engagement, seller actor, offer terms and version | Shared case participants; offer is not purchase approval | Exchange records and party-bound offer actions; accept/counter remain distinct from buyer approval. |
| Approval request | Purchase intent identity/hash, policy/approver basis, outcome | Buyer organization; pending/approved/denied/superseded | Purchase routes and procurement gate; exact intent and current state must be rechecked. |
| Purchase intent | Immutable exact line items, amount/currency/recipient and expected fulfillment description, source decision | Buyer-private, locked and approval-bound; not an external purchase receipt | `python/domain/models.py::PurchaseIntent` and purchase intent/approval routes. |
| Payment handoff | Intent ID, URL, exact amount/currency/recipient/reference/expiry and status | Buyer-controlled external HTTPS destination; READY/OPENED/EXPIRED/CANCELLED are handoff states only | `PaymentHandoff` and open route require `can_execute_purchase` and step-up. Opening the destination is not a charge, settlement, entitlement, refund or fulfillment receipt. |
| Outcome checkpoint | Intent, state, source class/reference/hash/time | Buyer record; distinguish system observation, provider report and human attestation | Outcome API accepts attributed source classes; no provider-confirmed event feed was verified in this audit. |

Expected lineage for a decision is: mission → brief version → selected company-context versions → evidence/product observations → decision version → (optional release/consent/engagement) → offer version → purchase intent → approval → external handoff → attributed outcome checkpoint. Each edge is explicit; no later object retroactively proves an earlier claim.

## 4. Company-context field catalog

Keep the current six kinds; use typed payload fields with explicit unit, source, scope, owner and freshness where applicable. This is a content contract proposal. Do not create a second context database before demonstrating that the current item/version model cannot hold it.

| Current kind | Useful field families | Validation / review implications |
| --- | --- | --- |
| `REQUIREMENT` | Required capability, minimum control/evidence, compatibility, target outcome | Store criterion and `MUST` priority; unknown evidence is not a pass. |
| `CONSTRAINT` | Budget range and currency, timeline, region, team size, legal/procurement limit | Explicit unit/period, source and expiry; budget stays buyer-private until an authorized projection is reviewed. |
| `STACK` | Current products/editions, identity/data dependencies, APIs, installed agents/MCPs, owners | Distinguish observed, user-confirmed and inferred; include version/source and `CURRENT` status. |
| `POLICY` | Security/privacy/residency rules, vendor risk gates, approval thresholds and required approvers | Owner and authority required; agent may identify conflict, not rewrite policy. |
| `PREFERENCE` | Preferred vendor traits, usability, support model, optional compatibility | Never silently treat as hard gate; attach reason/weight only if evaluation contract accepts it. |
| `NOTE` | Context that may help but is not a formal criterion | Must not become a hard gate or external disclosure without explicit classification/review. |

Recommended shared metadata per fact: `source_class`, `source_reference`, `observed_at`, `valid_until` or review cadence, `confidence`, `scope`, `owner`, `privacy`, and a user-confirmed state. Current schemas persist an exact JSON payload, version/hash and change reason; verify which metadata is currently enforced before rendering these as structured controls.

## 5. Action/authority matrix

| Action | Proposed authorized actor | Current implementation signal | UI rule |
| --- | --- | --- | --- |
| Read buyer context / mission | Buyer party with `can_view_context` | Route permissions and tenant scoping | Show buyer-private label; do not include in seller projections. |
| Edit/retire company context | Buyer human with `can_manage_procurement_gate` | Human identity, capability, idempotency key and `If-Match` required | Preview fields/reason/version and affected mission before saving. |
| Discover products / research public sources | Buyer or seller workspace within its party scope | Marketplace research and catalog commands | Label public-web observation and last-seen time; research does not publish seller evidence. |
| Edit seller draft | Seller editor for owning organization | Seller party and seller workflow checks | Keep private; show publication state distinctly. |
| Review/publish/suspend evidence | Authorized seller reviewer/publisher | Server workflow actor/role validation | Exact revision, gaps, buyer-safe projection and effect on catalog must be reviewed. |
| Release buyer requirement | Authorized buyer human | Current brief, expiry and allowlist checks in exchange service | Recipient, purpose, exact fields and version shown before release. |
| Consent to introduction | Required authorized participant on each side | Current consent/introduction endpoints | No unilateral disclosure; show fields, recipient, purpose, expiry and decline path. |
| Respond / counter / accept offer | Actor from owning exchange party and supported commercial authority | Party-specific exchange commands | Exact terms/version visible; agreement remains separate from purchase approval. |
| Approve intent | Buyer with approval permission and valid policy; role-specific approver routing needs validation | Approval routes and step-up boundaries | Exact commitment, policy basis, approver and current version required. |
| Open external payment handoff | Buyer execution authority with step-up | Exact handoff route | Name external merchant, amount/currency/reference and expiry; explain opening does not verify purchase. |
| Connect data source / run MCP / provision product | Specific admin or scoped user grant and implemented provider/tool capability | No verified provider or runtime lifecycle for these examples | Hide/disable until a capability contract and server enforcement exist; never collect secrets in chat. |
| Confirm outcome | Provider evidence or attributed human reporter | Checkpoint API has source classes; provider callback not established | Label source and timestamp; preserve unknown/inconclusive state. |

The service is the authority. The interface must consume explicit server capability projection for action visibility. Client state, workspace name, conversational permission or disabled button never substitutes for server authorization.

## 6. Information-release policy

Safe proposed defaults pending policy-owner approval:

1. Company context, budget, competing offers, internal strategy, security incidents and private source documents remain buyer-private.
2. A buyer brief starts private. The release step creates a specific recipient/purpose/version-bound, seller-safe projection from an allowlist; never send raw company context or free-form chat by default.
3. Seller drafts, internal source files, reviewer notes, margins and lead-scoring details remain seller-private. Publication exposes only reviewed allowlisted product evidence and explicit terms intended for buyers.
4. Public-web facts and seller attestations retain distinct source labels. A citation match is provenance, not a proof guarantee.
5. Before buyer/seller contact exchange, both required parties review the exact contact fields, recipient, purpose and expiry. No required consent means no introduction.
6. A later version or policy change does not silently alter an already released record. Supersede/revoke future access where supported and preserve an audit history; delivered information cannot be made unseen.
7. Notifications contain only a minimal status and safe deep link. Do not put brief text, budgets, credentials, raw evidence or offer terms in unverified channels.

These are product defaults for design and review; publish or enforce policy only through the accountable business/security decision process.

## 7. Business decision register

| Decision | Safe interim default | Owner / dependency | Effect while open |
| --- | --- | --- | --- |
| Buyer organization membership and delegated approver routing | No role claim beyond server-projected capability; keep human approval explicit | Business owner + identity/admin implementation | Do not claim configurable approval chains. |
| Seller reviewer and commercial signing authority | Require currently supported seller workflow actor; do not infer from title | Seller business owner | Do not claim legal signature or contract execution. |
| Platform fees, commissions, buyer billing and sales terms | No public fee/pricing claim | Business owner | Keep pricing details out of launch claims until approved. |
| Supported geography, currency and taxes | Only accept exact currencies/amounts supported by contracts; no tax estimate | Finance/legal owner + category implementation | Do not localize estimates or promise tax-inclusive totals. |
| Notification channels and response SLA | In-app state only; no response-time promise | Product/business owner + integration | No Slack/Teams/email delivery or seller SLA claim. |
| Source retention, imported-company-data retention and deletion | Follow existing approved policy; do not invent a new duration | Privacy/security owner | Suite connectors remain off; surface current policy before connection work. |
| First launch cohort and category | Meeting-intelligence SaaS is the proposed product slice | Product/business owner | Step 11/14 launch cohort remains uncommitted. |
| Purchase cancellation, refunds, deployment and entitlement truth | External provider/contract is authoritative; platform state remains unknown unless evidence arrives | Finance/procurement and integration owner | No automated cancellation/refund/deployment/fulfillment claims. |

## 8. Step 01 completion state

Role jobs, the object lineage, current context kinds and safe release defaults are specified. Business positioning and the no-unapproved-commercial-terms rule are explicit. Organization membership/approver assignment, seller signing authority, business fees, geography/currency policy, retention, notifications and launch-cohort decisions remain unresolved dependencies. Their dependent UI promises/actions stay out of scope until owners decide them.
