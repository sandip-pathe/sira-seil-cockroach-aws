import type { ReactNode } from "react";

import styles from "./form-field.module.css";

type FormFieldControlProps = {
  id: string;
  "aria-describedby": string;
  "aria-invalid"?: true;
};

type FormFieldProps = {
  id: string;
  label: string;
  helpText?: string;
  error?: string;
  required?: boolean;
  children: (controlProps: FormFieldControlProps) => ReactNode;
};

/** A labeled form control with stable, accessible help and error associations. */
export function FormField({
  id,
  label,
  helpText,
  error,
  required = false,
  children,
}: FormFieldProps) {
  const helpId = helpText ? `${id}-help` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [helpId, errorId].filter(Boolean).join(" ");

  return (
    <div className={styles.field} data-invalid={Boolean(error)}>
      <label htmlFor={id}>
        {label}
        {required ? <span className={styles.required}>Required</span> : null}
      </label>
      {children({
        id,
        "aria-describedby": describedBy,
        ...(error ? { "aria-invalid": true as const } : {}),
      })}
      {helpText ? (
        <p id={helpId} className={styles.help}>
          {helpText}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className={styles.error}>
          {error}
        </p>
      ) : null}
    </div>
  );
}
