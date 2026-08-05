# Agent boundary

`sira_agents` contains SIRA/SEIL orchestration and model guardrails. It is a
separate import root so the internal code does not shadow the top-level
`agents` package supplied by the OpenAI Agents SDK.

The root agent is the adaptive control plane for planning, investigation,
evaluation, ranking, recommendation, and bounded delegation. Its claims become
inspectable artifacts with provenance; they are not silently promoted to facts.
Identity, capability grants, approval authority, payment state, publication,
and Stackfile activation remain deterministic server operations outside this package.
