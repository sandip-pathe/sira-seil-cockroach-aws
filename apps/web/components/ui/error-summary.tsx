import type { RefObject } from "react";

import styles from "./error-summary.module.css";

export type FieldError = { id: string; label: string; message: string };

/** Focusable, linked summary for correcting a multi-field form in one pass. */
export function ErrorSummary({
  errors,
  summaryRef,
}: {
  errors: FieldError[];
  summaryRef?: RefObject<HTMLElement | null>;
}) {
  if (!errors.length) return null;
  return (
    <section ref={summaryRef} className={styles.summary} role="alert" aria-labelledby="form-error-summary-title" tabIndex={-1}>
      <h4 id="form-error-summary-title">Review these fields</h4>
      <ul>
        {errors.map((error) => (
          <li key={error.id}>
            <a href={`#${error.id}`}>{error.label}: {error.message}</a>
          </li>
        ))}
      </ul>
    </section>
  );
}
