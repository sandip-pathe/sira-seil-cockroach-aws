# Shared interaction primitives

Step 04.2 remains in progress. This increment extracts reusable patterns from consequential product flows rather than creating a component catalog without consumers.

## Native modal dialog

`apps/web/components/ui/modal-dialog.tsx` wraps the browser's native `<dialog>` modal behavior. The SEIL “Submit revision for review” action uses it.

- It enters the top layer with `showModal()`, so the browser contains keyboard focus within the open modal and makes the rest of the page inert to interaction.
- Initial focus enters the labeled modal container rather than the primary confirmation button.
- Native Escape cancellation becomes an explicit close request. While submission is pending, cancellation is prevented; close and confirmation controls are disabled by the owning flow.
- On unmount, the dialog closes and focus returns to the element that opened it when that element is still connected.
- The user-facing content explains that submission freezes the exact revision for review; it does not publish the Pack or verify unsupported claims.
- `aria-labelledby`, `aria-describedby`, modal semantics and alert-dialog intent remain attached to the native element.

The modal uses the shared backdrop and viewport limits in `apps/web/app/globals.css`, with seller-specific width/content styling in `seller-surfaces.module.css`.

## Labeled field, help and error

`apps/web/components/ui/form-field.tsx` now associates a label, optional required indicator, help text and inline error with the consuming control. It passes the stable control `id`, `aria-describedby` and conditional `aria-invalid` attributes to the child input. The shared styles provide a 44 px minimum control height and visible focus state.

The exchange offer form uses this pattern. Its annual USD amount starts empty, so the interface does not imply a suggested price. The field explains that it becomes the exact commercial term, accepts up to two decimal places, and uses native required/pattern validation plus an inline message after the field is blurred. Submission still goes through the existing versioned, idempotent offer mutation.

## Validation and limits

The modal increment passed `pnpm check:web`, `pnpm build:web`, and all 16 Playwright desktop/mobile route and accessibility scenarios. Those scenarios do not reach the authenticated submit-review action, so they do not exercise open/cancel/return-focus end to end. The local product-view probe also did not provide a review action; that interaction needs a test fixture or authorized test tenant before claiming full journey verification.

The labeled-field increment passed the web check and production build. The current browser scenarios do not exercise the exchange form, so the buyer/seller offer submission journey remains unverified in browser automation.

## Next primitives, selected by repeated need

1. A focusable linked error summary for multi-field submissions.
2. Shared status and notice treatment that keeps source, authority and uncertainty text visible.
3. Empty, loading and error states that preserve retry and return context.

Extract each only when a current flow uses it. Preserve accessible names and keyboard behavior in consuming components.
