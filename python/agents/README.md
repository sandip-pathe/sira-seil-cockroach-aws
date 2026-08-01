# Agent boundary

`sira_agents` contains SIRA/SEIL orchestration and model guardrails. It is a
separate import root so the internal code does not shadow the top-level
`agents` package supplied by the OpenAI Agents SDK.

Model output is advisory extraction or explanation only. Eligibility,
ranking, approval authority, payment state, and Stackfile activation remain
deterministic operations outside this package.
