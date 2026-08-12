# Product design contract

Do not redesign the application. Keep the existing SIRA/SEIL sidebar, chat, and right-hand inspector. Change the information order and states.

## Design rule

The buyer must understand this before seeing infrastructure:

> The lower-cost option was eligible. The seller corrected its hosting region. That option became blocked. SIRA restarted and recommended the option that still fits.

Reliability is supporting proof, not the headline.

## Information architecture

### SIRA chat

1. Buyer request.
2. Compact evaluation progress.
3. Evidence-change notice.
4. Final recommendation card.
5. `Open decision details`.

### SIRA decision inspector

1. **Outcome** — recommendation, blocked alternative, one-sentence reason.
2. **What changed** — v1 `EU hosting available`; v2 `US-only`; lower-cost option blocked.
3. **Company requirements**.
4. **Compared options**.
5. **Evidence and versions**.
6. **Run integrity**, collapsed by default — restart, worker recovery, duplicate suppression, and product-side integrity verdict. Do not call it MCP output unless it actually came through MCP.

### SEIL inspector

1. Product and publication state.
2. Current published version.
3. Claims and evidence.
4. Hosting-region correction.
5. `Publish v2 correction`.
6. `Active buyer evaluation affected` confirmation.

## Critical states

```text
SIRA — evaluating
┌ Chat ─────────────────┬ Decision inspector ────────────┐
│ Finding the best fit  │ Checking company fit           │
│                      │ EU hosting        Required      │
│                      │ Lower-cost option v1 Eligible   │
│                      │ Snapshot locked   4 sources     │
└──────────────────────┴─────────────────────────────────┘
```

```text
SEIL — correction
┌ Vendor chat ──────────┬ Product evidence ──────────────┐
│ Correct hosting       │ Lower-cost option              │
│ availability          │ Published v1: EU available     │
│                      │ New v2: US-only                 │
│                      │ [Publish correction]            │
└──────────────────────┴─────────────────────────────────┘
```

```text
SIRA — changed outcome
┌ Chat ─────────────────┬ Decision inspector ────────────┐
│ Evidence changed.     │ WHAT CHANGED                   │
│ Restarting with v2.   │ EU available → US-only         │
│                      │ Lower-cost option now blocked   │
│                      │ Old attempt: no decision        │
└──────────────────────┴─────────────────────────────────┘
```

```text
SIRA — final
┌ Chat ─────────────────┬ Decision inspector ────────────┐
│ Recommendation ready  │ Privacy-safe option            │
│ [Open decision]       │ Meets EU-hosting requirement   │
│                      │ Lower-cost option: BLOCKED      │
│                      │ Run integrity ▸ PASS            │
└──────────────────────┴─────────────────────────────────┘
```

## State transitions

| From | Trigger | User-visible state | Visual priority |
|---|---|---|---|
| Ready | Buyer starts | `Checking company requirements` | Normal |
| Snapshot v1 | Evaluation begins | v1 and EU requirement visible | Normal |
| v1 → v2 | SEIL publishes correction | `Evidence changed` and exact field diff | High |
| Invalidated | Finalization sees v2 | `Old attempt: no decision issued` | High |
| Interrupted | Worker stops | `Resuming from saved checkpoint` | Low |
| Resumed | New worker claims | `Resumed after interruption` | Low |
| Complete | v2 evaluation ends | winner and blocked alternative | Highest |
| Product checked | SQL integrity check ends | collapsed `Run integrity: PASS` | Secondary |

## Component changes

Keep:

- workspace shell;
- product cards and mission history;
- seller-published and research-only labels;
- keyboard focus treatment;
- responsive drawer behavior;
- reduced-motion and forced-colors support.

Remove from the active product:

- `DataHubCitedDecisionPanel`;
- Snowflake decision and approval copy;
- proof-workspace surfaces;
- sponsor-specific result cards;
- long URNs, hashes, raw JSON, and infrastructure text in the default view;
- old fixture product and vendor brands in the recorded scenario.

Build:

- one sponsor-neutral decision panel with an outcome-changing version diff;
- one compact `What changed` component;
- one collapsed `Run integrity` disclosure;
- short status cards instead of long agent prose;
- `aria-live` announcements for invalidation, recovery, and completion;
- icon plus text for every pass, block, warning, and error state;
- preserved inspector context when it becomes a mobile overlay.

## Responsive and accessibility contract

- Record at 1440 × 900 or wider; below 840 px the inspector becomes an overlay.
- At mobile width, the user can close and reopen the inspector without losing selected decision or scroll position.
- The final recommendation and blocked option are visible before the integrity disclosure.
- Do not rely on color alone.
- Status changes announce once and do not steal focus.
- Demo controls have explicit labels and are absent outside demo mode.
- Reduced-motion mode removes animated progress without hiding state changes.

## Silent-video test

Without audio, a viewer must be able to answer:

1. What did the buyer require?
2. Which seller fact changed?
3. Which option became blocked?
4. Did the stale attempt issue a decision?
5. What did SIRA finally recommend?
6. Did integrity checks pass?

If any answer requires a voiceover, the screen hierarchy is not ready.

No graphical mockups were generated during planning because the local gstack design binary was unavailable. These text wireframes are the build contract; validate the implemented states with screenshots before freeze.
