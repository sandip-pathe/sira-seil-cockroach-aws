"use client";

import type { ReversalView } from "@sira/api-client";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { buyerDevelopmentHeaders, createIdempotencyKey, getBrowserApiClient } from "@/lib/api";

import styles from "./payment-reconciliation.module.css";

export function PaymentReconciliation({ intentId }: { intentId: string }) {
  const refundKey = useRef(createIdempotencyKey(`refund-${intentId}`));
  const [reversal, setReversal] = useState<ReversalView | null>(null);
  const status = useQuery({
    queryKey: ["purchase-status", intentId],
    queryFn: () =>
      getBrowserApiClient().request("purchase_status", {
        pathParams: { intent_id: intentId },
        headers: buyerDevelopmentHeaders,
      }),
    refetchInterval: (query) => {
      const state = query.state.data?.purchase_state;
      return state && ["PAYMENT_IN_PROGRESS", "PAYMENT_UNCERTAIN", "REFUND_PENDING"].includes(state)
        ? 3000
        : false;
    },
  });
  const refund = useMutation({
    mutationFn: () =>
      getBrowserApiClient().request("request_purchase_reversal", {
        pathParams: { intent_id: intentId },
        headers: buyerDevelopmentHeaders,
        idempotencyKey: refundKey.current,
        body: {
          kind: "REFUND",
          reason_code: "BUYER_REQUESTED_REVERSAL",
          reason: "Buyer requested a refund from the canonical purchase result.",
        },
      }),
    onSuccess: (result) => {
      setReversal(result);
      void status.refetch();
    },
  });

  if (status.isLoading) return <section className={styles.panel}>Loading payment state...</section>;
  if (status.error) {
    return (
      <section className={styles.panel} role="alert">
        <strong>Payment state unavailable</strong>
        <p>The browser return is not payment proof. Retry the canonical server-side status.</p>
        <button type="button" onClick={() => void status.refetch()}>
          Retry status
        </button>
      </section>
    );
  }
  if (!status.data) return null;
  const uncertain = status.data.purchase_state === "PAYMENT_UNCERTAIN";
  const paid = status.data.payment_status === "PRAVA_COMPLETED";

  return (
    <section className={styles.panel} aria-live="polite">
      <div>
        <small>Canonical purchase state</small>
        <h3>{status.data.purchase_state.replaceAll("_", " ")}</h3>
        <p>
          {uncertain
            ? "The provider outcome is uncertain. SIRA reconciles this attempt and will not create a blind duplicate charge."
            : paid
              ? "PRAVA payment is reconciled. Fulfillment remains a separate verification gate."
              : "This state comes from the server-side purchase record, not the browser return."}
        </p>
      </div>
      <div className={styles.actions}>
        <button type="button" disabled={status.isFetching} onClick={() => void status.refetch()}>
          {status.isFetching ? "Refreshing..." : "Refresh reconciliation"}
        </button>
        {paid && !reversal ? (
          <button type="button" disabled={refund.isPending} onClick={() => refund.mutate()}>
            {refund.isPending ? "Requesting..." : "Request refund"}
          </button>
        ) : null}
      </div>
      {reversal ? (
        <p>
          <strong>Reversal {reversal.status.replaceAll("_", " ")}</strong> - refunded{" "}
          {reversal.currency} {reversal.refunded_amount} of {reversal.requested_amount}. Provider
          confirmation: {reversal.provider_confirmed ? "yes" : "pending"}.
        </p>
      ) : null}
      {refund.error ? (
        <p role="alert">The reversal was not created. The existing payment state is unchanged.</p>
      ) : null}
    </section>
  );
}
