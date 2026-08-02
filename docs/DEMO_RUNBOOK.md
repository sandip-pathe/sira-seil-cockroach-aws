# SIRA + SEIL Demo Runbook

Updated: 2026-08-02 against `79663fa`  
Audience: presenter, click operator, and whoever is recovering the demo  
Target: a truthful three-minute hackathon demonstration that survives local or provider failure

## The decision

Use one of these modes. Decide before opening the presentation.

| Mode | Use when | What may be claimed |
|---|---|---|
| **A — Deterministic decision demo** | Always available after the web fixture loads | A fixed ConsultCo scenario demonstrates company-aware evaluation, seller `PASS`, action-neutral alternatives, deterministic ranking, counterfactual reasoning, evidence, audit hash, and a proposed Stackfile change. |
| **B — API-backed fixture demo** | PostgreSQL migrations, API health, reset, and the full browser smoke test pass | Everything in A, plus persisted request/version/state and the exact selected-plan snapshot. Do not claim live Senso or live purchasing. |
| **C — Live sandbox purchase demo** | B passes and Prava, Temporal, controlled merchant, HTTPS return, entitlement, and recovery drills all pass immediately before the demo | A bounded Purchase Intent is approved, executed through sandbox Prava, reconciled with the merchant, and followed by verified entitlement and a staged Stackfile patch. |

Default to **Mode A**. Upgrade to B or C only when every gate for that mode is green. Never improvise a higher claim on stage.

## Non-negotiable claims boundary

Say this near the start:

> “This is a fixed, fictional ConsultCo scenario. The decision, gates, ranking, hashes, and counterfactual are deterministic. Provider-backed purchasing is shown only if today’s sandbox certification is green.”

Safe core claim:

> “SIRA deterministically evaluates seller-published SEIL evidence against frozen company context, explains every gate and ordering decision, shows what changes the answer, and proposes an auditable Stackfile change.”

Do not claim any of the following unless Mode C passed its preflight:

- arbitrary company requests are dynamically compiled into decisions;
- live Senso retrieval changed this decision;
- an LLM or autonomous agent selected the winner;
- a real merchant was charged;
- a real entitlement was provisioned;
- post-purchase outcomes already improve future decisions;
- the system is production-ready.

The labels `Development fixture`, `sandbox`, and `not production` must remain visible. Never hide them for presentation polish.

## One presentation stop condition

The current fixture contains ten evaluated actions, including:

- Product A at USD 49, blocked by the buyer's no-customer-training policy;
- Product B at USD 79, returning seller-authored `SEIL_PASS` because the required shared-client workspace is unsupported;
- reuse, configure, resize, renew, cancel, and no-action alternatives;
- Product D at USD 89 as the company-aware winner.

The current Options component uses `view.solution_options.slice(0, 6)` in `apps/web/components/decisions/decision-surfaces.tsx`. It therefore hides Product A, Product B, cancel, and no-action from the visible table.

**Do not deliver the intended company-context/PASS demo until the UI visibly exposes at least:**

1. recommended Product D;
2. generic cheap Product A with the buyer-policy blocker;
3. Product B with the seller `PASS` reason;
4. one existing-tool action;
5. one do-not-buy/no-action outcome;
6. an explicit counterfactual label: **without company context → Product A; with company context → Product D**, naming restricted client conversations (`bf_restricted_client_conversations`) as a decisive fact.

This is the highest-value remaining presentation change. The table may show all rows, group them as Recommended / Alternatives / Blocked, or add a compact “Why not the others?” section. The proof must be visible without opening source code or Swagger.

## Roles during the demo

Use two people when possible.

- **Presenter:** speaks, watches time, and chooses the fallback.
- **Click operator:** follows only the numbered click path, does not explore, and announces failures quietly.
- **Recovery operator (optional):** watches API/web/worker terminals and opens the prepared fallback artifact when told.

The presenter owns one decision: if a screen does not settle within three seconds, say the prepared recovery sentence and move on. Do not debug live.

## T-minus 30 minutes: freeze the demo

1. Stop feature work on the demo branch.
2. Record the exact revision:

   ```powershell
   git rev-parse --short HEAD
   git status --short
   ```

3. Do not pull, merge, install, regenerate fixtures, migrate, or change `.env` after the final successful rehearsal.
4. Close notifications, terminals with secrets, unrelated browser tabs, password managers, and personal applications.
5. Disable browser extensions that inject UI or translate text.
6. Use a 1280×720 or 1440×900 browser viewport at 100% zoom. Do not use mobile for the judged run.
7. Put the five stage URLs below in a bookmarks folder named `DEMO`.
8. Rehearse once from a fresh browser tab while screen recording.
9. Save the recording and screenshots outside the repository on the presentation machine.

## T-minus 15 minutes: choose the mode

### Mode A check

Start fixture web mode in a dedicated PowerShell window:

```powershell
$env:NEXT_PUBLIC_WEB_DATA_MODE = "fixture"
$env:NEXT_PUBLIC_DEVELOPMENT_IDENTITY = "true"
corepack pnpm dev:web
```

Open `http://localhost:3000/decisions/req_demo/versions/1/company-fit`.

Mode A is green only when:

- the fixture banner is visible;
- Company fit shows eight facts;
- Options shows every required proof listed under the stop condition;
- the generic-versus-company counterfactual is visible without opening source code;
- `Open ledger` works;
- the page survives one refresh;
- browser console has no application error;
- the same winner and decision hash remain after refresh.

### Mode B check

Mode B additionally requires PostgreSQL and API mode:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\migrate.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-api.ps1
```

In a separate PowerShell window:

```powershell
$env:NEXT_PUBLIC_WEB_DATA_MODE = "api"
$env:NEXT_PUBLIC_DEVELOPMENT_IDENTITY = "true"
corepack pnpm dev:web
```

Verify health:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Required result: `status` is `ok`, `database` is `configured`, and the expected fixture mode is explicit. A degraded health result means immediate fallback to Mode A.

Reset the fixed development scenario only when nobody else is using that database:

```powershell
$demoHeaders = @{
  "X-Organization-Id" = "org_consultco"
  "X-Actor-Id" = "usr_demo_requester"
  "X-Actor-Party" = "BUYER"
  "X-Actor-Roles" = "can_submit_request,can_view_context,can_select_recommendation,can_manage_procurement_gate,can_approve_purchase,can_execute_purchase"
  "X-Step-Up-Verified" = "true"
  "X-Identity-Kind" = "HUMAN"
}
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/demo/reset -Headers $demoHeaders
```

Then run the exact browser path once. If selection, version transition, refresh recovery, or the expected hash fails, return to Mode A.

### Mode C check

Do not infer readiness from unit tests. Mode C requires all of these live sandbox facts:

- Temporal worker is connected and its organization allowlist includes `org_consultco`;
- Prava, controlled merchant, callback, hosted checkout, and HTTPS web-return values are configured;
- the selected offer produces an exact Purchase Intent from the persisted selected plan;
- approval, expiry, and revocation are visible and enforced;
- a browser return resumes backend reconciliation rather than declaring success;
- the controlled merchant returns one order for the idempotency key;
- entitlement is verified independently from payment;
- the receipt identifies sandbox/non-production provenance;
- the Stackfile patch is `STAGED`, not falsely `ACTIVE`;
- the latest drills for pending, timeout before dispatch, timeout after dispatch, duplicate attempt, and paid-but-unfulfilled recovery produced no duplicate merchant order.

Start the worker only after those settings are present:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-worker.ps1
```

Any missing provider value, HTTP callback, failed drill, or uncertain state means Mode C is red. Do not “try it anyway” in front of judges.

## T-minus 2 minutes: browser setup

Open these exact pages in order, one tab each:

1. `http://localhost:3000/decisions/req_demo/versions/1/need`
2. `http://localhost:3000/decisions/req_demo/versions/1/company-fit`
3. `http://localhost:3000/decisions/req_demo/versions/1/options`
4. `http://localhost:3000/seller/product-evidence/product_fixture_d`
5. The certified Action/Result URL only for Mode B or C

Keep the first tab selected. Pre-scroll Company fit to the decisive facts and Options to the recommendation/blocked rows. Close Next dev tools and any debug overlays.

Write these four values on paper; never hunt for them on stage:

- company-aware winner: **Product D, USD 89 / 30 days**;
- generic cheap candidate: **Product A, USD 49 / 30 days**;
- seller PASS candidate: **Product B, USD 79 / 30 days**;
- decision hash prefix: **`sha256:6ccfcb60…`** for the frozen fixture at revision `79663fa`. Reconfirm after any fixture regeneration.

For a certified Mode B fixture-authority walkthrough, also write down: merchant `merchant_fixture_d`; USD 89 total comprising USD 87 merchant subtotal plus a USD 2 **demo-only** buyer fee; expected workspace plus ten-seat entitlements; intent hash prefix `sha256:13a8a511…`. These are fictional fixture records, not proof of live Prava or production pricing.

## Three-minute script — Mode A

This is the default script. It deliberately demonstrates the strongest real product behavior and stops before fake transaction success.

| Time | Operator action | Presenter says | Visible proof | If it fails |
|---:|---|---|---|---|
| 0:00–0:15 | Show **Need**. Do not type into the disabled conversation. | “Buying software is not a search problem. The same product can be right for one company and wrong for another. This fixed scenario is a ten-person consulting team deciding whether to keep, resize, or replace its meeting-intelligence tool.” | Existing tool, ten seats, deadline, desired outcome, and separate operations/budget/cardholder roles. | Open the prepared Need screenshot and continue. |
| 0:15–0:45 | Switch to **Company fit**. Point to restricted client conversations, no customer-data training, source-linked answers, native integrations, low admin capacity, and budget. | “SIRA freezes the company facts that can change the answer. Private budget and Stack data stay on the buyer side; sellers receive only the minimum Requirement Brief.” | Eight versioned facts with provenance and sensitivity; disclosure boundary. | Use the Company-fit screenshot. Say “The live shell failed; this is the same frozen input.” |
| 0:45–1:25 | Switch to **Options**. Point first to Product A, then Product B, then reuse/no-action, then Product D. Do not scroll randomly. | “A generic price-first search chooses Product A at 49 dollars. SIRA rejects it because it violates the company’s customer-data policy. Product B honestly returns PASS because this team needs a shared-client workflow it does not support. Reuse and do-not-buy remain real options. With company context, Product D is the best supported action—not simply the cheapest product.” | Product A buyer-policy blocker; Product B seller PASS; existing-tool/no-action row; Product D recommended at USD 89. | If any of these rows is absent, do not make that claim. Use the prepared Options screenshot or switch to the short engine-proof slide. |
| 1:25–2:05 | Click **Open ledger**. Point to stability, evaluated plans, evidence authority, evidence frontier, exact hash, engine, and company-profile version. | “The LLM does not decide eligibility or rank. Deterministic code evaluates gates and exact bounds. The ledger records the evidence, what could change the result, and the exact versions and hash needed to replay it.” | Stable result, ten evaluated plans, evidence records, named frontier, decision hash, `engine_v1`, Profile v1. | Open the ledger screenshot. Do not open API docs. |
| 2:05–2:30 | Close ledger; show the selected option’s Stack change. | “A recommendation is not execution. SIRA proposes a Stackfile change and keeps selection, approval, payment, fulfillment, deployment, and outcome as separate states.” | Proposed replacement/retained dependencies; no false payment or outcome success. | Stay on screenshot and speak the state separation. |
| 2:30–2:50 | Switch to **SEIL Product Evidence**; open the Fit tab if necessary. | “SEIL is the seller-controlled truth layer. Sellers publish reusable claims and anti-fit rules once. Positioning can explain a product, but it has zero ranking weight.” | Versioned Product Evidence, fit/anti-fit rules, evidence/publication status. | Use the SEIL screenshot. |
| 2:50–3:00 | Return to Options recommendation. | “The result is a company-specific, explainable action—not a sponsored ranking—and the same decision record is ready to become bounded purchasing authority when the certified sandbox path is enabled.” | Product D recommendation and fixture label remain visible. | End on the Options screenshot. |

The New Decision fixture form ignores edited request content and opens this same fixed result. Never type a custom request during the demo and imply that it produced the decision.

### Words to avoid

Do not say:

- “AI picked the best product.”
- “Senso found these facts live.”
- “We bought it.”
- “The payment succeeded.”
- “The Stackfile is updated.”
- “The system learns automatically.”
- “This works for any category or company.”

Prefer:

- “best supported action among the evaluated options”;
- “frozen company context”;
- “seller-published Product Evidence”;
- “proposed Stackfile change”;
- “exact, bounded authority”;
- “sandbox-certified” only after the Mode C gate passes.

## Mode B extension — persisted authority proof

Use this only when the API-backed browser smoke test passes. Replace the final 30 seconds of Mode A:

1. Select Product D.
2. Show that a new immutable Decision version is created.
3. Show the exact selected-plan snapshot: merchant, amount, currency, line items, Pack, offer, quote, expected entitlement, decision hash, and proposed Stack patch.
4. Show approval as a separate state.
5. Revoke or expire a prepared duplicate approval and show that execution is unavailable.

Say:

> “Prava is not a checkout button added at the end. The selected offer becomes exact authority before payment. A different merchant, higher amount, expired approval, or revoked approval cannot reuse it.”

Stop there unless Mode C is green. A backend test or model state is not a successful purchase.

## Mode C extension — sandbox execution proof

Replace the final 55 seconds of Mode A only after certification:

1. Show the locked Purchase Intent summary before leaving the app.
2. Start Prava hosted authorization through the visible, server-authorized action.
3. Complete only the prepared sandbox authorization. Never enter a real card or production credential.
4. Return to SIRA and say nothing about success until backend reconciliation settles.
5. Show, in order:
   - payment confirmation;
   - merchant order reference;
   - expected entitlement verified;
   - sandbox receipt;
   - Stackfile patch staged;
   - later outcome still pending.
6. Show the prepared blocked attempt: expired or revoked approval, wrong merchant, or amount above authority. Confirm no checkout control or merchant side effect.

Say:

> “The browser redirect is not proof. SIRA reconciles Prava, the merchant order, and the entitlement. Only then does it issue a sandbox receipt and stage the Stackfile change. Outcome remains a later checkpoint.”

## Failure routing during the presentation

| Symptom | Maximum wait | Presenter sentence | Operator action |
|---|---:|---|---|
| Page blank, 500, or hydration failure | 3 s | “I’ll use the frozen evidence from the same deterministic run.” | Open matching screenshot or recording timestamp. |
| API health degraded / database unavailable | 0 s | “The canonical database path is unavailable, so I’m switching to the labelled deterministic fixture.” | Switch to Mode A tabs. |
| Decision differs after refresh | 0 s | “This run is not reproducible, so I won’t present it as verified.” | Use last certified recording; flag the live path red. |
| Product A or Product B missing | 0 s | “The current view filtered a required proof, so I’ll show the certified comparison artifact.” | Open Options proof screenshot; do not verbally invent hidden rows. |
| Select/approve action disabled | 0 s | “Execution is intentionally unavailable in this fixture.” | Continue with ledger and state-boundary story. |
| Prava handoff does not open | 3 s | “The sandbox dependency is unavailable; no payment authority or success will be inferred.” | Return to Mode A/B and show the locked intent only. |
| Hosted return remains pending | 5 s | “The result is uncertain, so duplicate checkout is blocked while reconciliation continues.” | Show pending/uncertain state, then use recording. Never retry manually. |
| Merchant timeout after dispatch | 0 s | “We do not know whether money moved, so the safe action is reconciliation—not another charge.” | Show uncertain state/recording. Do not start again. |
| Payment confirmed, entitlement missing | 0 s | “Payment is confirmed; product success is not. The system remains paid-but-unfulfilled.” | Show recovery state; do not claim completion. |
| Internet fails | 0 s | “The core decision is local and deterministic; provider execution requires the sandbox network.” | Complete Mode A offline. |

## Required fallback pack

Prepare these after the final green rehearsal. Do not reuse older captures after a fixture/hash change.

| Artifact | Required content | Suggested filename |
|---|---|---|
| Need screenshot | Fixed request, incumbent, seats, deadline, roles | `01-need.png` |
| Company-fit screenshot | All decisive facts, provenance, disclosure boundary | `02-company-fit.png` |
| Options screenshot | Product D, Product A blocker, Product B PASS, reuse/no-action, and the generic-versus-company counterfactual | `03-options.png` |
| Ledger screenshot | Stability, evidence, frontier, full hash/version | `04-ledger.png` |
| SEIL screenshot | Published evidence and fit/anti-fit rules | `05-seil-pack.png` |
| Intent screenshot, Mode B/C | Merchant, amount, currency, line items, expiry, hash | `06-purchase-intent.png` |
| Guardrail screenshot, Mode B/C | Expired/revoked/wrong amount blocked | `07-guardrail.png` |
| Result screenshot, Mode C | Sandbox payment, order, entitlement, receipt, staged patch | `08-result.png` |
| Screen recording | One uninterrupted certified run with fixture/sandbox labels visible | `certified-demo.mp4` |
| Proof note | Revision, mode, timestamp, decision hash, browser, provider sandbox IDs | `certified-demo.txt` |

Keep the fallback pack in one local folder and one offline copy. Do not put provider credentials, tokens, cookies, emails, full logs, or payment data in any capture.

The click operator should know the recording timestamps for Company fit, Options, ledger, authority, and result. If live execution fails, jump directly to the matching timestamp rather than replaying from the beginning.

## One-minute emergency script

If the schedule is cut or the live app is unstable:

1. Show Company fit screenshot: “These frozen private facts define what fit means for this company.”
2. Show Options screenshot: “Cheap Product A fails buyer policy; Product B honestly passes; reuse and no-buy remain options; Product D wins with company context.”
3. Show Ledger screenshot: “Deterministic gates and exact bounds produce a replayable decision hash; the model does not control rank.”
4. Show Intent/guardrail screenshot only if certified: “The selected offer becomes exact authority, and unsafe execution is blocked.”
5. End: “SIRA connects company truth, seller truth, and controlled execution without turning uncertainty into fake success.”

## Judge questions and short answers

### “Is this just ChatGPT recommending software?”

No. Models may extract or explain, but deterministic Python owns gates, evidence status, bounds, ranking, tie-breaking, counterfactuals, hashes, and authority. The ledger is derived from the calculation.

### “Why will sellers tell the truth or return PASS?”

SEIL separates reusable published claims and anti-fit rules from buyer-specific positioning. Positioning has zero rank weight. A seller can avoid a bad-fit implementation by declaring an anti-fit rule once; the buyer sees the exact PASS reason and Pack version. Long-term reputation and verified outcome scoring are planned, not yet claimed.

### “What changes because of company context?”

The generic price-first candidate is Product A at USD 49. ConsultCo requires no customer-data training, restricted client-conversation handling, source-linked answers, compatible integrations, and low administration effort. Product A fails policy; Product D becomes the best supported action at USD 89.

### “Can SIRA recommend not buying?”

Yes. Reuse, configure, resize, renew, cancel, and no-action are first-class plans evaluated with the same gates and dimensions. In this fixed scenario Product D wins; the engine is not required to select a purchase.

### “How do you stop seller manipulation?”

Ranking consumes typed, versioned claims and evidence assessments. Seller positioning is excluded from rank. Buyer hard gates run before preferences. Pack authority, verification, freshness, and provenance remain separate. Marketplace reputation and broad adversarial-content certification remain future work.

### “Why is Prava necessary?”

The recommendation and the authority to spend are different objects. Prava executes only after SIRA binds the exact merchant, amount, currency, line items, quote/offer versions, payer, expiry, expected entitlement, and decision hash. It is the constrained execution layer, not merely a payment button.

### “Can approval be reused or changed?”

The application binds approval to the exact intent hash. Expiry and revocation are rechecked before hosted session creation, browser return, and final dispatch. A different merchant, amount, currency, or intent requires new authority. Claim this as live only after the API-backed/sandbox smoke test passes.

### “Do payment credentials enter the model or browser?”

No. The hosted flow and worker isolate the one-time credential. Workflow contracts reject credential-like fields; the browser, database, logs, traces, and Temporal history receive only safe identifiers and outcomes.

### “How do you know a purchase succeeded?”

A redirect is never enough. The system must reconcile Prava, the merchant order, and expected entitlement. Payment, fulfillment, Stack deployment, and business outcome are separate states.

### “What is real today and what is mocked?”

Real today: the deterministic fixed-scenario graph, typed gates, ranking, counterfactual, hashes, ledger, state models, safety checks, and labelled UI. Fixture-backed today: the company/products/evidence in the default demo. Not yet claimed: arbitrary company compilation, live Senso-driven choice, production identity, general marketplace, real purchasing, and outcome learning.

### “What is the business?”

The initial wedge is governed software renewal and replacement for teams where context, policy, duplicated tools, and implementation risk matter. The buyer pays for decision and procurement control; seller participation must remain neutral, with no pay-to-rank behavior. Pricing shown in the current UI is not yet a committed commercial offer.

### “What is defensible?”

The implemented entry surface is now chat-first, but chat is not the defensible asset. The asset is versioned company context, Stackfile state, seller-authored Product Evidence, and the deterministic Decision Ledger. The intended moat adds verified transaction outcomes and, once implemented with consent, a learning loop connecting seller claims to observed results.

## Final go/no-go card

The presenter reads this card 60 seconds before starting:

- [ ] I know whether we are in Mode A, B, or C.
- [ ] I will say that the core scenario is fixed and fictional.
- [ ] Product A, Product B PASS, Product D, existing-tool, and no-action proof are visible.
- [ ] The decision hash is stable after refresh.
- [ ] The fixture/sandbox label is visible.
- [ ] I have the final screenshots and certified recording open locally.
- [ ] I will not debug for more than three seconds.
- [ ] I will never interpret a redirect, workflow completion, or payment alone as product success.
- [ ] I will stop before purchasing if sandbox certification is not green.
- [ ] I can answer “what is real versus mocked?” in one sentence.

If any of the first six items is false, use the one-minute emergency script. If sandbox certification is false, use Mode A or B. There is no circumstance in which the demo uses a real payment instrument.

## After the demo

1. Record which mode was shown and whether a fallback was used.
2. Save the visible decision hash, revision, and sandbox references without credentials.
3. Do not describe a fixture or fallback recording as a live provider result in the submission.
4. Convert judge questions into product-validation notes; do not patch the demo branch during judging.

## Related evidence

- `docs/DEMO_READINESS_LEDGER.md` — current implementation and live-certification gates.
- `docs/QUALITY_AUDIT.md` — pre-fix full quality audit; consult the readiness ledger for later fixes.
- `docs/BUILD_SPEC.md` — first integrated product contract.
- `README.md` — local setup, startup, verification, and provider requirements.
