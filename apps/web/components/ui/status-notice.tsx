import type { ReactNode } from "react";

import styles from "./status-notice.module.css";

type StatusNoticeProps = {
  tone: "info" | "success" | "warning" | "error";
  title?: string;
  children: ReactNode;
  action?: { label: string; onAction: () => void; disabled?: boolean };
};

/** A concise live status with an optional recovery action. */
export function StatusNotice({ tone, title, children, action }: StatusNoticeProps) {
  return (
    <section
      className={styles.notice}
      data-tone={tone}
      role={tone === "error" ? "alert" : "status"}
      aria-atomic="true"
    >
      <div className={styles.copy}>
        {title ? <strong>{title}</strong> : null}
        <div>{children}</div>
      </div>
      {action ? (
        <button type="button" onClick={action.onAction} disabled={action.disabled}>
          {action.label}
        </button>
      ) : null}
    </section>
  );
}
