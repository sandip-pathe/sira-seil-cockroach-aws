# Chat-first workspace flow

This document is the UI/backend contract for the redesigned SIRA and SEIL workspace. It supersedes the previous buyer flow that opened a separate intake, decisions, or inbox page.

## Layout invariant

The authenticated product stays on `/sira` or `/seil` and keeps three surfaces:

1. Left sidebar for chats and workspace actions.
2. Centre chat for intent, follow-up questions, explanations, and inline components.
3. Right contextual pane for lists and details. It is part of the main desktop grid and can be collapsed or expanded.

Settings and user details open as a modal over this layout. Old SIRA URLs such as `/sira/decisions`, `/sira/inbox`, and `/decisions/new` redirect to `/sira`.

## Action map

| User action | Centre chat | Right pane | Backend source |
|---|---|---|---|
| New chat | Empty conversational intake | Agent run | `POST /v1/workspace/chat` |
| Describe a buying need | SIRA asks one material follow-up at a time | Run/progress | Workspace chat; later structured decision APIs |
| Ask to browse or compare | Catalogue cards appear inline | Catalogue list | `GET /v1/workspace/catalog` and chat response products |
| Click a product | Card remains in transcript | Product Evidence detail | `GET /v1/workspace/catalog/{product_id}` contract |
| Decisions sidebar button | Chat remains mounted | Decisions state | Existing decision-request APIs |
| Connectors sidebar button | Chat remains mounted | Business Context, Senso, DataHub, and other sources | `GET /v1/workspace/connectors` |
| Inbox sidebar button | Chat remains mounted | Assigned work; honest empty state when none exists | Task/workflow state when implemented |
| Profile/settings | Chat remains mounted behind overlay | Unchanged | Settings modal; authenticated profile when connected |
| Attach company context | Drafts a chat request and opens connectors | Connector choice/setup | Context-source APIs when implemented |

## Agent boundary

The model is a conversational context collector and explainer. It may ask for outcome, users, deadline, constraints, budget, approval path, and missing evidence. It receives only recent authorized conversation context and published catalogue facts. It cannot rank candidates, make a Decision Record, approve, purchase, pay, publish seller claims, or activate software. Those actions remain deterministic, permission-checked, idempotent backend workflows.

## Current persistence boundary

Catalogue facts come from server-side Product Evidence fixtures in development. Chat history is currently kept in the browser and the most recent messages are sent with each request; canonical conversation persistence is not yet implemented. Decision and execution records remain PostgreSQL-backed. The UI must not imply that an unpersisted chat is an approved decision.

## Failure states

- Missing `SIRA_OPENAI_API_KEY`: composer remains usable and shows the server's configuration error in the transcript. Docker maps this project-scoped variable to the provider SDK's internal `OPENAI_API_KEY`; a global Windows/Codex key is intentionally ignored.
- Provider failure or invalid model response: show a retryable assistant error; never substitute invented catalogue output.
- Missing connector: lower confidence or block only the dependent action; allow chat/manual context when policy permits.
- No inbox assignments: show an honest empty state, never a fake badge.
