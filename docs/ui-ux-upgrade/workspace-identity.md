# Workspace identity and party context

## Shipped UI behavior

The chat header persistently identifies SIRA as the buying workspace or SEIL as the selling workspace and displays the privacy scope currently available to the client. The current `/sira` and `/seil` routes are party-locked, so the user-facing workspace switch is intentionally absent until authenticated organization membership is available. The underlying conversation state is mode-keyed, and mode changes clear the active decision selection and composer if a unified switch is enabled later.

The client does not show an organization name from demo fixtures or infer one from an email address. Account identity and organization identity are different facts.

## Contract required to complete organization identity

The workspace bootstrap or a dedicated authenticated endpoint must return an authoritative active-workspace projection with at least:

- stable `organization_id` and a server-approved display name;
- active party (`BUYER` or `SELLER`) and the organizations/workspaces available to the actor;
- effective membership state and permissions for that organization and party;
- an explicit unavailable/denied state when membership is missing, revoked, or unresolved.

Every read and mutation must continue to enforce organization membership, party ownership, and action permission server-side. A client-side workspace switch is a presentation/context choice; it cannot grant access. The response should be the source for the persistent organization label and should be invalidated after organization switch, membership change, or authentication change.

## Completion checks

1. Show the server-provided organization label alongside the active party in the workspace shell.
2. Load only conversations and context scoped to the authorized organization and party.
3. On a denied or revoked workspace, clear organization-scoped selections and show an actionable access state without presenting cached data as current.
4. Verify buyer-to-seller switching, organization switching, refresh, revoked membership, and direct-route access against server authorization, including cache isolation.

Until this contract is available in the typed client, the UI should retain neutral account-level identity and avoid claiming organization membership has been verified.
