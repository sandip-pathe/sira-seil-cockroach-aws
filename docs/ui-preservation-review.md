# Restored UI preservation agreement

Status: **frozen; review notes only; no UI work is authorized.**

The current SIRA and SEIL interface is the product's visual baseline. It was restored from
commit `b6f98554c8c43407d3f9bb672bd2c2d5712614aa` and must remain recognizably identical while
the CockroachDB, agent runtime, evidence, exchange, and AWS work is completed behind it.

## What is frozen

- SIRA and SEIL route structure and navigation.
- The sidebar, conversation canvas, composer, inspector, cards, dialogs, profile surfaces,
  decision pages, evidence pages, typography, color, spacing, borders, icons, and motion.
- Existing responsive behavior and interaction rhythm.
- The visual component library and design language. No replacement shell or second design
  system may be introduced.
- The current user-facing product vocabulary unless an individual error message is inaccurate,
  unsafe, or exposes implementation details.

Backend integration must adapt to the UI contracts. The UI must not be redesigned to make a
backend implementation easier.

## Work allowed without a separate design approval

- Fix a broken API call, stale state, authentication error, or inaccessible control while leaving
  its rendered appearance unchanged.
- Feed existing components with durable CockroachDB data instead of fixtures.
- Replace a raw exception, tool name, database term, or false success claim with truthful natural
  language in the same component and visual treatment.
- Correct focus, labels, keyboard behavior, screen-reader announcements, reduced motion, or a
  small-screen overflow defect without changing the visible composition.
- Add test IDs or non-visual accessibility metadata.

These are repairs, not permission to reinterpret the interface.

## Work explicitly deferred

- New pages, dashboards, navigation sections, side panels, cards, timelines, or workflow builders.
- Changes to layout, typography, spacing, colors, component shapes, animation, or information
  hierarchy.
- A new chat shell, agent-console aesthetic, technical trace UI, or infrastructure dashboard.
- Moving controls, consolidating screens, or replacing existing interaction patterns.
- Adding visible CockroachDB, Bedrock, AgentCore, tool-call, checkpoint, or runtime branding to
  ordinary user flows.
- Any speculative polish prompted by automated design review.

## Current behavioral findings (not design proposals)

The current `/sira` surface renders the restored interface correctly. A live browser check found
that a greeting reached the cloud Bedrock adapter during local mode and displayed the existing
safe failure card. That is a runtime-profile defect. The fix belongs in local runtime selection;
the card and surrounding UI do not need redesign.

The bilateral workflow needs to project these already-defined product states into the current
components:

1. SIRA asks one material question when context is insufficient.
2. The current decision surface shows the exact seller-visible disclosure before approval.
3. SEIL receives only the approved projection and publishes cited evidence.
4. SIRA explains comparison, uncertainty, and counterfactuals in existing result surfaces.
5. The existing confirmation treatment shows exact offer terms and opens an external handoff
   without claiming payment occurred.

This is functional wiring and truthful data projection, not authorization to change how those
surfaces look.

## Approval gate for any future UI proposal

Before changing a visible pixel, prepare a review-only package containing:

- the exact user problem and evidence that the current UI cannot support it;
- screenshots of the current desktop and mobile states;
- a smallest-possible proposed change using current components;
- before/after screenshots and a route-level visual diff;
- accessibility and behavioral impact;
- a simple rollback path.

No proposed UI change is implemented until the founder explicitly approves that package. A
backend requirement, automated review finding, or hackathon rubric is not approval.
