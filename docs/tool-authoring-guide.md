# Typed tool authoring guide

The model can see and invoke only tools that pass the deterministic broker. Adding a function to a
Python registry is not enough.

## Current rule

Model-visible kernel tools are authenticated reads. Business mutations stay in deterministic
application services and human-confirmed API routes. Add a model-visible mutation only when its
aggregate version, idempotency, authorization, retry, and recovery semantics are explicit. A
protected effect additionally requires an exact single-use capability.

## Add a tool

1. Define one `ToolManifest` with a stable snake-case name and version.
2. Declare exact principals, parties, purposes, allowed stages, and risk.
3. Use a closed JSON input schema with `additionalProperties: false`, bounds, and required fields.
4. Define a bounded output schema containing only data safe for that principal.
5. Implement a handler through an application-service protocol. Do not import SQLAlchemy,
   persistence models, HTTP transport, or AWS clients into the agent-contract package.
6. Derive organization, actor, roles, and party from `ContextManifest`; never accept them as model
   arguments.
7. Repeat object ownership and permission checks in the application service.
8. Add success and denial tests for wrong principal, party, purpose, stage, version, extra field,
   tenant/object, stale object version, timeout, invalid output, and budget exhaustion.

## Mutation/effect additions

- mutation: one serialized aggregate command, `expected_version`, idempotency key, maximum one per
  turn, and database-only retry closure;
- protected effect: all mutation rules plus payload hash, actor, principal, party, purpose, object
  versions, expiry, use count, transactional reservation, durable receipt, and reconciliation of
  uncertain external outcomes;
- never perform network/model work inside the Cockroach transaction;
- never compose success until the durable result or receipt exists.

## Review gate

Reject the change if the tool can access the opposing private plane, takes an organization/role
from model input, has an open object schema, returns unbounded raw documents, duplicates business
logic, changes state without an expected version, or can retry an external effect blindly.

Relevant implementation: `python/agents/sira_agents/kernel_models.py`, `tool_broker.py`,
`kernel_tools.py`, and `services/api/sira_api/cognitive_engine.py`.
