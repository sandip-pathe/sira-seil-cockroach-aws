# Shared interaction primitives

Step 04.2 status: in progress. This increment extracts the highest-risk repeated primitive that is already used in a consequential product flow; it does not claim the entire component inventory is complete.

## Native modal dialog

`apps/web/components/ui/modal-dialog.tsx` wraps the browser's native `<dialog>` modal behavior. The SEIL “Submit revision for review” action now uses it.

- The component enters the top layer with `showModal()`, so the browser contains keyboard focus within the open modal and makes the rest of the page inert to interaction.
- Initial focus enters the labeled modal container rather than the destructive/primary confirmation button.
- Native Escape cancellation is translated to an explicit close request. While submission is pending, cancellation is prevented; close and confirmation controls are disabled by the owning flow.
- On unmount, the dialog closes and focus returns to the element that opened it when that element is still connected.
- The user-facing content remains explicit: submitting freezes the exact revision for review; it does not publish the Pack or verify unsupported claims.
- `aria-labelledby`, `aria-describedby`, modal semantics and `alertdialog` intent remain attached to the native element.

The modal uses the shared backdrop and viewport limits in `apps/web/app/globals.css`, with seller-specific width/content styling in `seller-surfaces.module.css`.

## Validation and limits

After this change, `pnpm check:web`, `pnpm build:web`, and all 16 Playwright desktop/mobile route and accessibility scenarios passed. The current browser scenario set does not reach the authenticated submit-review action, so it does not exercise the open/cancel/return-focus behavior end to end. The product API did not provide a review action in the local product-view probe. That interaction needs a test fixture or authorized test tenant before claiming full journey verification.

## Next primitives, selected by repeated need

1. A field/help/error association used by company-context and offer forms.
2. A focusable linked error summary for multi-field submissions.
3. Shared status and notice treatment that keeps source, authority and uncertainty text visible.
4. Empty/loading/error states that preserve retry and return context.

Extract each only when a current flow uses it. Avoid creating a component catalog disconnected from product screens. Preserve accessible names and keyboard behavior in consuming components.
