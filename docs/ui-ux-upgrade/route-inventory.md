# Route and entry inventory

Audit date: 2026-10-21. Evidence is a static source audit of `apps/web/app`, route components, and their direct surface components. This does not claim a manual browser pass for every route.

| Route | Surface / owner | Behavior and entry notes |
| --- | --- | --- |
| `/` | Public landing; SIRA + SEIL | Buyer/seller entry and product narrative; primary public entry. |
| `/pricing`, `/security`, `/privacy`, `/terms` | Public information | Claims and legal/security summaries require the Step 12 claim reconciliation. |
| `/sign-in`, `/sira/sign-in`, `/seil/sign-in` | Public auth | Shared or workspace-specific sign-in entry points. Seller save/publish requires a real configured Firebase account. |
| `/sira` | SIRA workspace | Main buyer workspace. Reads `decision`, `version`, `stage`, and `panel=decisions`; stages accepted: `need`, `company-fit`, `options`, `action`, `result`; invalid stage falls back to `options`; invalid decision/version yields no initial decision. |
| `/seil` | SEIL workspace | Main seller workspace, catalog context. |
| `/seil/inbox` | SEIL inbox | Seller attention list. |
| `/seil/products/search` | SEIL product search | Seller product lookup/search. |
| `/seil/product-evidence/[productId]` | Seller evidence workspace | Product evidence with optional `field` focus query. |
| `/exchange/[caseId]` | Governed exchange room | Seller/buyer exchange keyed by case; detailed authorization is enforced server-side. |
| `/sira/settings/profile`, `/seil/settings/profile` | Profile modal over workspace | Separate workspace context and profile modal. |
| `/decisions` | Alias | Redirects to `/sira/decisions`, then `/sira?panel=decisions`. |
| `/sira/decisions` | Alias | Redirects to `/sira?panel=decisions`. |
| `/decisions/new` | Alias | Redirects to `/sira`. |
| `/decisions/[requestId]/versions/[version]/[stage]` | Decision deep link | Valid stage redirects to `/sira?decision=…&version=…&stage=…`; invalid stage invokes not-found. |
| `/sira/inbox` | Alias | Redirects to `/sira`. |
| `/home`, `/inbox`, `/settings/profile` | Legacy aliases | Redirect to `/`; destination is the public landing, not an authenticated workspace. Confirm this is intentional before route redesign. |
| `/seller` | Legacy alias | Redirects to `/seil`. |
| `/seller/products/search` | Legacy alias | Redirects to `/seil/products/search`. |
| `/seller/product-evidence/[productId]` | Legacy alias | Redirects to `/seil/product-evidence/[productId]`, preserving encoded `field`. |
| Framework error/not-found | Error recovery | `app/error.tsx` offers home recovery; `app/not-found.tsx` offers return to SIRA + SEIL home. Workspace auth/error recovery is not route-specific in these surfaces. |

## Entry-path issues to carry forward

- Public routes are distinct from workspace routes; authentication/session behavior is owned by the workspace layout and service authorization, not inferred from the URL name.
- Legacy `/inbox` and profile aliases send users to `/`, while role-specific settings/inbox routes exist. Verify inbound-link and browser-history expectations before changing destinations.
- Decision deep links preserve request/version/stage in the query string, so refresh/share behavior depends on the SIRA page's query parser and data authorization.
- Exchange route ownership is shared workflow state; the path identifier does not itself grant access.
- Seller evidence alias preserves a single `field` value. Repeated `field` values collapse to the first.

## Source map

- Route definitions: `apps/web/app/(public)` and `apps/web/app/(workspace)`.
- Buyer workspace: `apps/web/app/(workspace)/sira/page.tsx`, `apps/web/components/workspace/commerce-workspace.tsx`.
- Seller workspace and evidence: corresponding SEIL route files and `apps/web/components/seller/seller-surfaces.tsx`.
- Exchange: `apps/web/app/(workspace)/exchange/[caseId]/page.tsx`, `apps/web/components/exchange/exchange-room.tsx`.
