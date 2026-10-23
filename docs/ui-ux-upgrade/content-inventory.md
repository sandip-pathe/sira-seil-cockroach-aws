# Customer-facing content inventory (baseline)

Audit date: 2026-10-21. This is a claim-and-surface inventory for Step 00. It identifies source owners and dependencies; it is not a rewritten copy deck.

| Content surface | Source | Main content and claim dependencies |
| --- | --- | --- |
| Landing hero, audience doors, product explanation, process, privacy/control sections, CTA, footer | `apps/web/components/public/landing-page.tsx` and its CSS module | Claims about choosing, approving, executing and verifying supported actions; private buyer context; reviewed seller evidence; human control and payment. Claims must map to current contracts and actual outcome signals. |
| Pricing, security, privacy, terms | `apps/web/components/public/public-secondary-pages.tsx` plus public route files | Business/legal/security policy; requires business/legal owner validation before launch. |
| Page title and description | Public and workspace `page.tsx` metadata; `apps/web/app/layout.tsx` | SIRA/SEIL role descriptions, indexing/social descriptions, and correct workspace naming. |
| Buyer workspace headings, navigation, quick prompts, demo agent responses, connector explanations, recommendation and evidence language | `apps/web/components/workspace/commerce-workspace.tsx` | Source truth, fixture labels, connector readiness, approval/purchase implication, candidate/product freshness, disclosure boundaries. Several messages currently call payment/merchant fulfillment “setup” or “connectors”; distinguish unavailable from merely disconnected. |
| Seller search, product editor, evidence review, publication and field-level guidance | `apps/web/components/seller/seller-surfaces.tsx` and related style modules | Draft privacy, evidence provenance, reviewer authority, publication visibility, source freshness, withdraw/revise consequences. |
| Seller inbox and buyer decision list | `apps/web/components/home/inbox-page.tsx` and associated components | Status, next owner, seller response usefulness, consent/action deadlines, empty/error/loading states. |
| Exchange room, terms, consent, offer and handoff states | `apps/web/components/exchange/exchange-room.tsx` | Exact party, amount/currency, recipient/reference, role authority, expiry, external completion boundary and uncertain outcome. |
| Sign-in and auth errors | `apps/web/app/(public)/*sign-in*`, auth components in `apps/web/components` | Buyer vs seller identity, account readiness, return destination, session failure, seller Firebase configuration. |
| Global error and not-found | `apps/web/app/error.tsx`, `apps/web/app/not-found.tsx` | Recovery destination and preservation of the user's current task/context. |
| Generated/agent messages and summaries | `commerce-workspace.tsx`, server response schemas/services, `apps/web/components/workspace/chat-message.tsx` | Separate verified facts, inference, missing information, proposed edits, applied actions and persistent artifact links. Never infer authority from generated text. |
| Notifications and external follow-up | No verified outbound notification template/delivery integration identified in this audit | Treat as unavailable until destination, consent, payload, delivery, retry and deep-link contracts are demonstrated. |
| Product and seller source labels | Product evidence and workspace product cards | Currentness, seller attestation vs public-web observation, source identity, and evidence quality; source citation membership does not independently prove claim accuracy. |

## Immediate content defects / checks

1. Workspace connector examples include Google Workspace, Slack, Zoom, payment/fulfillment language, and messages saying source connections are healthy. The server connector contract currently returns only manual Business Context setup and Google Workspace “Not connected.” Make each card state its exact unavailable/not connected/setup state.
2. Landing page language includes “execute, and verify” supported actions and a distinct human-controlled payment/fulfillment boundary. Preserve only where the linked human-operated handoff and outcome checkpoints support it; do not imply platform-verified payment or fulfillment.
3. Marketing outcome lists mention cancel, renew, resize, replace, and buy. Each action requires a mapped contract, external effect, owner and recovery state; the current audit has not demonstrated all of those end-to-end.
4. Demo product cards/messages should be visibly labeled as examples and must not be used as current market facts or pricing evidence.
5. Pricing and legal/security language need an accountable business review; repository text alone cannot establish policy approval.

Copy key catalog from `docs/ui-ux-upgrade/copy-spec.md` remains the source for future implementation IDs. Add exact string keys and state variants during Step 02 rather than duplicating a second copy system here.
