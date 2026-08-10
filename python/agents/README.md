# Agent package boundary

`sira_agents` is a separate import root so project code does not shadow the `agents` package from the OpenAI Agents SDK.

Agents may plan, investigate, explain, and recommend. Identity, permissions, approvals, publication, payment state, and decision eligibility remain deterministic server operations outside this package.
