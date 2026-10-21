"use client";

import { useEffect, useRef, type ReactNode } from "react";

type ModalDialogProps = {
  children: ReactNode;
  labelledBy: string;
  describedBy?: string;
  className?: string;
  alert?: boolean;
  busy?: boolean;
  onRequestClose: () => void;
};

/** Native modal dialog with focus entry/return and an explicit cancel boundary. */
export function ModalDialog({
  children,
  labelledBy,
  describedBy,
  className,
  alert = false,
  busy = false,
  onRequestClose,
}: ModalDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const closeRef = useRef(onRequestClose);
  const busyRef = useRef(busy);

  useEffect(() => {
    closeRef.current = onRequestClose;
    busyRef.current = busy;
  }, [busy, onRequestClose]);

  useEffect(() => {
    const dialog = dialogRef.current;
    const previousFocus =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    if (!dialog) return;

    dialog.showModal();
    dialog.focus();

    return () => {
      if (dialog.open) dialog.close();
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, []);

  return (
    <dialog
      ref={dialogRef}
      data-ui-modal="true"
      className={className}
      role={alert ? "alertdialog" : "dialog"}
      aria-modal="true"
      aria-busy={busy || undefined}
      aria-labelledby={labelledBy}
      aria-describedby={describedBy}
      tabIndex={-1}
      onCancel={(event) => {
        event.preventDefault();
        if (!busyRef.current) closeRef.current();
      }}
    >
      {children}
    </dialog>
  );
}
