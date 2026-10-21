# SIRA + SEIL semantic design tokens

Initial shared-token implementation for Step 04.1. The palette extends the existing product foundation; the structural flow is still a proposal and the tokens do not imply prototype validation.

## Semantic roles

| Role | CSS custom property | Value | Use |
| --- | --- | --- | --- |
| Canvas / surface | `--canvas` / `--surface` | `#faf9f5` / `#ffffff` | Quiet workspace canvas and primary reading surface. |
| Main / muted text | `--text` / `--muted` | `#2d2c29` / `#6f6a61` | Main facts and secondary metadata. Essential state/action text must not rely on muted color alone. |
| SIRA / SEIL | `--sira`, `--sira-soft`, `--sira-hover` / `--seil`, `--seil-soft`, `--seil-hover` | `#0b5fff`, `#eaf0ff`, `#0847c7` / `#7c3aed`, `#f3e8ff`, `#5b21b6` | Party identity and relevant actions; never status meaning. |
| Status | `--success`, `--warning`, `--danger`, `--info` and matching backgrounds | Existing token values | Pair status color with text/icon and explicit state wording. |
| Focus | `--focus`, `--focus-width`, `--focus-offset` | `#1d4ed8`, `2px`, `2px` | Visible keyboard focus. Do not remove for pointer styling. |
| Reading fonts | `--font-ui`, `--font-mono`, `--font-brand` | Geist Sans, Geist Mono, restrained Montserrat | Readable decisions; exact IDs/code; product identity. |

## Scale

- Spacing: `--space-1` through `--space-7` = 4, 8, 12, 16, 24, 32, 48 px.
- Type: 12, 14, 16, 18, 20, 24, 32, 40 px (`--text-xs` through `--text-3xl`). Body uses 16 px and 1.5 line height; 12 px is reserved for nonessential metadata and must be checked at zoom/reflow.
- Radius: 6 px controls, 10 px panels, 16 px dialogs, pill for compact status chips.
- Elevation: restrained card and popover shadows; dialogs can use the existing overlay shadow.
- Layers: sticky 10, menu 20, overlay 40, dialog 50, toast 60. Use the lowest layer that meets the interaction need.
- Motion: 120/180/240 ms fast/standard/slow with a shared standard easing. Reduced-motion preference continues to remove animation and smooth scrolling globally.
- Target: `--touch-target-min: 44px` is the minimum for new primary touch controls; existing compact/dense controls need a separate exception review.

## Verification recorded

The initial contrast calculation used WCAG relative luminance on the shared foreground/background pairs below. All sample text pairs exceeded 4.5:1:

| Pair | Contrast |
| --- | ---: |
| Main text on canvas | 13.25:1 |
| Muted text on white | 5.37:1 |
| SIRA / hover on white | 5.13:1 / 7.67:1 |
| SEIL / hover on white | 5.70:1 / 8.98:1 |
| Success / warning / danger on matching background | 5.19:1 / 5.41:1 / 5.75:1 |
| Info on info background | 5.80:1 |

These calculations cover the listed token pairs, not every component/state combination, images, browser rendering, or WCAG conformance. The global base text changed from 15 px to 16 px. The workspace now consumes shared color, font, focus and motion tokens. `pnpm check:web`, `pnpm build:web`, and 16 Playwright desktop/mobile scenarios passed after this change.

## Remaining Step 04 work

- Audit repeated literal values across CSS modules and migrate only where semantics match; avoid mass replacements that change component meaning.
- Check actual component contrast and hover/disabled/error/selected combinations, forced colors, high zoom and long content.
- Apply the 44 px target to newly touched controls and audit existing icon controls for adequate hit area.
- Verify layout at the playbook's wide, compact, narrow, 320 px and 200% zoom targets with visual browser review.
