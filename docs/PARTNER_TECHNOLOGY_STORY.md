# Partner Technology Story

**Evidence snapshot:** 2026-08-02, branch `core-backend`, revision `79663fa`  
**Audience:** judges, collaborators, and public repository readers  
**Scope:** Prava, Visa through Prava, Senso, and OpenAI. Temporal is project infrastructure, not an event partner.

## The story in one paragraph

SIRA does not use partner technology as a row of logos. Senso supplies scoped, versioned company evidence; OpenAI turns that untrusted material into typed fact proposals; SIRA's deterministic Decision Graph decides what is eligible and ranks supported plans; Prava turns the exact approved plan into bounded payment authority. Visa-track eligibility comes through the real Prava integration. Temporal coordinates credential-free execution and recovery, but is not presented as a hackathon partner.

The strongest demonstration is:

> Company evidence changes the eligible choice → SIRA locks the exact merchant, amount, currency, line items, expiry, and expected entitlement → an unsafe mutation is visibly blocked → Prava authorizes the valid instruction → merchant result and entitlement are reconciled → Stackfile and the later outcome record are updated.

## Honest integration scorecard

| Technology | Necessary product role | Implemented value | Remaining proof |
|---|---|---|---|
| **Prava** | Cardholder authorization and scoped payment authority | Server-only hosted REST boundary; exact merchant/amount/order checks; non-serializable one-time credential; separate merchant and fulfillment reconciliation | Record one complete provider-backed sandbox flow and its recovery cases |
| **Senso** | Scoped evidence retrieval and provenance | Folder/grant checks, version-aware ingestion, exact source spans, adversarial-content flags, and human acceptance before evidence can affect a decision | Run one credentialed source-to-decision proof with a reconstructable citation |
| **OpenAI Agents SDK** | Typed interpretation of untrusted evidence | Structured fact proposals, allowlisted read-only tools, payload/trace restrictions, and no ranking or payment authority | Run and evaluate the composed provider-backed extraction path |
| **Visa VIC** | Intelligent-commerce award and product framing | Prava-mediated eligibility plus a decision-bound enterprise payment instruction | Make the Authority Diff and decision-to-entitlement proof visible; do not claim a direct Visa API integration |
| **Temporal** | Durable project execution and recovery | Credential-free workflow contracts, retries, reconciliation, and duplicate-side-effect controls in code/tests | Demonstrate retained-history crash/restart recovery against a live Temporal service |

Code and contract tests count as implementation evidence, not provider certification. Public claims move from **implemented** to **verified live** only when the corresponding sandbox record exists.

## Prava: more than a checkout button

Prava is the boundary between a recommendation and permission to spend. Before a Prava session is requested, SIRA freezes a Purchase Intent containing the selected plan, merchant, amount, currency, line items, quote and offer versions, payer, approval chain, expiry, expected entitlement, decision hash, and proposed Stackfile change.

The hosted REST adapter then:

1. creates a short-lived session for the exact order;
2. sends the user to Prava's cardholder authorization surface;
3. receives a constrained one-time credential only on the server;
4. checks provider session, order, merchant, and amount before merchant dispatch;
5. reports and reconciles the merchant result separately from entitlement verification.

Relevant implementation: `python/integrations/prava/rest.py`, `python/integrations/prava/models.py`, `services/api/sira_api/service.py`, and `services/worker/sira_worker/contracts.py`.

### Distinctive Visa/Prava proof: Authority Diff

The UI should show both a valid and invalid instruction:

```text
Approved: Merchant D / USD 89 / ten seats / exact quote
Attempted: Merchant X / USD 109 / changed line item
Result: blocked before payment authority is requested
```

This is stronger than “the agent clicked Buy.” It shows that requester intent, company policy, approver authority, payer consent, seller offer, and the final transaction remain bound to one instruction. Any material mutation requires new authority.

Do not claim that Prava completed a purchase until a recorded sandbox transaction exists. Do not claim a direct Visa API integration.

## Senso: evidence, not a ranking oracle

Senso stores and retrieves private source material with folder-scoped access and content versions. SIRA deliberately treats retrieved text as untrusted evidence:

- retrieval relevance is not truth confidence;
- exact document spans and versions are preserved;
- model output is only an advisory typed fact proposal;
- an authorized human must accept a proposal before it becomes company context;
- flagged prompt-injection or decision-manipulation content requires explicit review;
- seller access never includes the Buyer Passport or private Stackfile.

The prize-worthy proof is intentionally small: place one buyer policy in a private Senso folder, retrieve it through the scoped adapter, accept one provenance-bound fact, and show that the fact changes the deterministic winner. Then open the citation and reconstruct the exact source/version.

Relevant implementation: `python/integrations/senso/ingestion.py`, the Senso provider adapter, and `tests/unit/test_senso_ingestion.py`.

Do not claim live Senso changed the recommendation until that credentialed flow is recorded.

## OpenAI: interpretation without delegated authority

OpenAI is used where models are strong: extracting typed proposals from messy evidence, identifying missing information, and explaining a deterministic result. Models do not decide eligibility, calculate authoritative rank, approve spending, receive payment credentials, or declare fulfillment.

The meaningful composed flow is:

```text
Senso source → read-only evidence tool → typed OpenAI proposal
→ deterministic validation → human acceptance when required
→ frozen Decision Graph input → deterministic result → bounded explanation
```

The remaining proof is one real typed extraction plus evaluation evidence for schema adherence, unsupported claims, prompt-injection resistance, latency, cost, and explanation faithfulness.

## What we are intentionally not adding

- No direct Visa client merely for an additional logo; Prava already supplies the relevant track relationship.
- No Prava MCP integration while Seilnsara owns the application surface; hosted REST is the appropriate current boundary.
- No partner is allowed to rank products directly.
- No seller positioning is treated as evidence or score input.
- No live-provider claim is made from mocks, fixtures, or contract tests.

## Priority order

1. Complete and record one real Prava sandbox checkout.
2. Add the visible Authority Diff negative test.
3. Run one scoped Senso fact through the composed product flow and show it changing the winner.
4. Run and evaluate the OpenAI typed extraction around that fact.
5. Show the proof packet: evidence version, company-context change, exact authority, merchant result, entitlement, Stackfile effect, and outcome checkpoint.

Security-adjacent integration findings, provider feedback candidates, and personal contribution strategy are intentionally kept out of this public document.
