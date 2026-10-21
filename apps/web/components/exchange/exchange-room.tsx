"use client";

import type { ExchangeHandoffView, ExchangeProjectionView } from "@sira/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  BadgeCheck,
  Check,
  Copy,
  FileCheck2,
  LockKeyhole,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMemo, useRef, useState } from "react";

import { FormField } from "@/components/ui/form-field";
import { StatusNotice } from "@/components/ui/status-notice";
import {
  buyerDevelopmentHeaders,
  createIdempotencyKey,
  getBrowserApiClient,
  sellerEditorDevelopmentHeaders,
} from "@/lib/api";

import styles from "./exchange-room.module.css";

type Released = {
  requirement?: { requirement?: Record<string, unknown> };
  evidence?: { summary?: string; published_span_ids?: string[]; evidence_hash?: string };
  current_offer?: {
    offer_hash?: string;
    predecessor_hash?: string | null;
    proposer?: string;
    currency?: string;
    total?: string;
    rationale?: string;
    changed_terms?: string[];
  };
  approval?: { offer_hash?: string; approval_hash?: string };
};

function released(view: ExchangeProjectionView | undefined): Released {
  return (view?.released ?? {}) as Released;
}

export function ExchangeRoom({ caseId }: { caseId: string }) {
  const search = useSearchParams();
  const queryClient = useQueryClient();
  const route = search.get("route") ?? "";
  const mode = search.get("mode") === "seil" ? "seil" : "sira";
  const isSeller = mode === "seil";
  const headers = isSeller ? sellerEditorDevelopmentHeaders : buyerDevelopmentHeaders;
  const [amount, setAmount] = useState("");
  const [amountTouched, setAmountTouched] = useState(false);
  const [notice, setNotice] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [handoff, setHandoff] = useState<ExchangeHandoffView | null>(null);
  const evidenceIntent = useRef<{ version: number; key: string } | null>(null);
  const queryKey = useMemo(() => ["exchange", caseId, route, mode], [caseId, route, mode]);

  const query = useQuery({
    queryKey,
    enabled: route.length >= 64,
    queryFn: () => getBrowserApiClient().request("get_exchange_case", {
      pathParams: { case_id: caseId },
      query: { route },
      headers,
    }),
  });
  const view = query.data;
  const data = released(view);
  const offer = data.current_offer;
  const amountError = !/^\d+(?:\.\d{1,2})?$/.test(amount) && amountTouched
    ? "Enter a USD amount with no more than two decimal places."
    : undefined;

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey });
  };

  const evidenceMutation = useMutation({
    mutationFn: () => {
      const version = view?.version ?? 0;
      if (evidenceIntent.current?.version !== version) {
        evidenceIntent.current = {
          version,
          key: createIdempotencyKey(`exchange-evidence-${caseId}-${version}`),
        };
      }
      return getBrowserApiClient().request("publish_exchange_evidence", {
        pathParams: { case_id: caseId },
        query: { route },
        body: {
          expected_version: version,
          summary: "Current published Product Evidence supports this requirement.",
          published_span_ids: [],
        },
        idempotencyKey: evidenceIntent.current.key,
        headers,
      });
    },
    onMutate: () => setNotice(null),
    onSuccess: async () => {
      evidenceIntent.current = null;
      setNotice({ tone: "success", text: "Evidence was submitted. Refreshing the exchange version." });
      await refresh();
    },
    onError: () => setNotice({ tone: "error", text: "No buyer-safe published evidence is available yet." }),
  });

  const offerMutation = useMutation({
    mutationFn: (expiresAt: string) => {
      const counter = view?.state === "OFFERED";
      return getBrowserApiClient().request("propose_exchange_offer", {
        pathParams: { case_id: caseId },
        query: { route },
        body: {
          expected_version: view?.version ?? 0,
          currency: "USD",
          lines: [{
            item_id: "workspace",
            description: "Ten-seat annual workspace",
            quantity: 1,
            unit_price: amount,
          }],
          total: amount,
          rationale: counter
            ? "Seller proposes one revised commercial term."
            : "Buyer proposes the evaluated annual workspace terms.",
          changed_terms: counter ? ["lines", "total"] : [],
          expires_at: expiresAt,
        },
        idempotencyKey: createIdempotencyKey(`${counter ? "counter" : "offer"}-${caseId}`),
        headers,
      });
    },
    onMutate: () => setNotice(null),
    onSuccess: refresh,
    onError: () => setNotice({ tone: "error", text: "Those terms were not recorded. Refresh the current version." }),
  });

  const acceptMutation = useMutation({
    mutationFn: () => getBrowserApiClient().request("accept_exchange_offer", {
      pathParams: { case_id: caseId },
      query: { route },
      body: { expected_version: view?.version ?? 0, offer_hash: offer?.offer_hash ?? "" },
      idempotencyKey: createIdempotencyKey(`accept-${caseId}-${offer?.offer_hash}`),
      headers,
    }),
    onMutate: () => setNotice(null),
    onSuccess: refresh,
    onError: () => setNotice({ tone: "error", text: "The offer changed or expired. Refresh before accepting." }),
  });

  const approveMutation = useMutation({
    mutationFn: (approvalExpiresAt: string) => getBrowserApiClient().request("approve_exchange_offer", {
      pathParams: { case_id: caseId },
      query: { route },
      body: {
        expected_version: view?.version ?? 0,
        offer_hash: offer?.offer_hash ?? "",
        approval_expires_at: approvalExpiresAt,
      },
      idempotencyKey: createIdempotencyKey(`approve-${caseId}-${offer?.offer_hash}`),
      headers,
    }),
    onMutate: () => setNotice(null),
    onSuccess: refresh,
    onError: () => setNotice({ tone: "error", text: "Recent buyer verification is required for exact-term approval." }),
  });

  const handoffMutation = useMutation({
    mutationFn: () => getBrowserApiClient().request("create_exchange_handoff", {
      pathParams: { case_id: caseId },
      query: { route },
      body: { expected_version: view?.version ?? 0, offer_hash: offer?.offer_hash ?? "" },
      idempotencyKey: createIdempotencyKey(`handoff-${caseId}-${offer?.offer_hash}`),
      headers,
    }),
    onMutate: () => setNotice(null),
    onSuccess: (result) => setHandoff(result),
    onError: () => setNotice({ tone: "error", text: "The approved offer could not be prepared for payment." }),
  });

  const openHandoffMutation = useMutation({
    mutationFn: () => {
      if (!handoff) throw new Error("Payment handoff not prepared");
      return getBrowserApiClient().request("open_exchange_handoff", {
        pathParams: { case_id: caseId, handoff_id: handoff.id },
        query: { route },
        body: { handoff_hash: handoff.handoff_hash },
        idempotencyKey: createIdempotencyKey(`open-handoff-${handoff.id}`),
        headers,
      });
    },
    onMutate: () => setNotice(null),
    onSuccess: (opened) => {
      setHandoff(opened);
      window.location.assign(opened.destination_url);
    },
    onError: () => setNotice({ tone: "error", text: "The payment page could not be opened. No payment was attempted." }),
  });

  const copySellerLink = async () => {
    const url = new URL(window.location.href);
    url.searchParams.set("mode", "seil");
    await navigator.clipboard.writeText(url.toString());
    setNotice({ tone: "success", text: "Seller link copied. It reveals no buyer tenant or private company context." });
  };

  if (route.length < 64) {
    return <main className={styles.shell}><section className={styles.empty}><LockKeyhole /><h1>{route ? "Exchange link incomplete" : "Exchange link required"}</h1><p>Open this room from a selected SIRA decision.</p></section></main>;
  }

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <Link href={isSeller ? "/seil" : "/sira"}><ArrowLeft /> {isSeller ? "SEIL" : "SIRA"}</Link>
        <div><small>{isSeller ? "Seller projection" : "Buyer projection"}</small><h1>Governed exchange</h1></div>
        <button type="button" onClick={() => void refresh()}><RefreshCw /> Refresh</button>
      </header>

      {query.isPending && route.length >= 64 ? <StatusNotice tone="info" title="Loading exchange">Checking the private exchange and its current version…</StatusNotice> : null}
      {query.isError ? <StatusNotice tone="error" title="Exchange unavailable" action={{ label: query.isFetching ? "Retrying…" : "Retry", onAction: () => void query.refetch(), disabled: query.isFetching }}>The link may be expired, or this account may not be an intended participant. No exchange action was recorded.</StatusNotice> : null}
      {view ? <>
        <section className={styles.statusBar}><span><ShieldCheck /> {view.state.replaceAll("_", " ")}</span><span>Version {view.version}</span><code>{view.projection_hash.slice(0, 24)}…</code></section>
        <div className={styles.grid}>
          <section className={styles.card}>
            <p>Released requirement</p>
            <h2>{String(data.requirement?.requirement?.intent ?? "Approved Requirement Brief")}</h2>
            <span>{String(data.requirement?.requirement?.desired_outcome ?? "Only the approved minimum-disclosure fields are visible here.")}</span>
            <div className={styles.boundary}><LockKeyhole /><span>Private buyer context and seller private values never enter this projection.</span></div>
          </section>

          <section className={styles.card}>
            <p>Published evidence</p>
            <h2>{data.evidence ? "Evidence bound" : "Waiting for seller evidence"}</h2>
            <span>{data.evidence?.summary ?? "Only already-published buyer-safe spans can cross."}</span>
            {isSeller && view.state === "REQUIREMENT_RELEASED" ? <button type="button" disabled={evidenceMutation.isPending} onClick={() => evidenceMutation.mutate()}><FileCheck2 /> Publish current evidence</button> : null}
          </section>

          <section className={styles.cardWide}>
            <div className={styles.offerHead}><div><p>Exact terms</p><h2>{offer ? `${offer.currency} ${offer.total}` : "No offer yet"}</h2></div>{offer ? <code>{offer.offer_hash?.slice(0, 28)}…</code> : null}</div>
            {offer ? <dl><div><dt>Proposed by</dt><dd>{offer.proposer}</dd></div><div><dt>Changed terms</dt><dd>{offer.changed_terms?.join(", ") || "Initial terms"}</dd></div><div><dt>Rationale</dt><dd>{offer.rationale}</dd></div></dl> : null}
            {(!isSeller && view.state === "EVIDENCE_RELEASED") || (isSeller && view.state === "OFFERED") ? <form className={styles.offerAction} onSubmit={(event) => { event.preventDefault(); offerMutation.mutate(new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString()); }}>
              <FormField id="exchange-annual-total" label="Annual total (USD)" required helpText="Enter the exact amount for this offer. USD amounts can have up to two decimal places." error={amountError}>
                {(controlProps) => <input {...controlProps} type="text" value={amount} inputMode="decimal" autoComplete="off" pattern="[0-9]+(\.[0-9]{1,2})?" required onBlur={() => setAmountTouched(true)} onChange={(event) => setAmount(event.target.value)} />}
              </FormField>
              <button type="submit" disabled={offerMutation.isPending}>{view.state === "OFFERED" ? "Send one counteroffer" : "Propose exact terms"}</button>
            </form> : null}
            {isSeller && view.state === "OFFERED" ? <button className={styles.secondary} type="button" disabled={acceptMutation.isPending} onClick={() => acceptMutation.mutate()}><Check /> Accept exact offer</button> : null}
            {!isSeller && view.state === "COUNTERED" ? <button type="button" disabled={acceptMutation.isPending} onClick={() => acceptMutation.mutate()}><Check /> Accept exact counteroffer</button> : null}
            {!isSeller && view.state === "AGREED_PENDING_APPROVAL" ? <button type="button" disabled={approveMutation.isPending} onClick={() => approveMutation.mutate(new Date(Date.now() + 15 * 60 * 1000).toISOString())}><BadgeCheck /> Approve for external handoff</button> : null}
            {view.state === "APPROVED_FOR_HANDOFF" ? <><div className={styles.complete}><BadgeCheck /><div><strong>Exact terms approved</strong><span>The provider-neutral payment handoff can now be prepared. Approval does not claim that money moved.</span></div></div>{!isSeller && !handoff ? <button type="button" disabled={handoffMutation.isPending} onClick={() => handoffMutation.mutate()}>{handoffMutation.isPending ? "Preparing…" : "Prepare payment handoff"}</button> : null}{!isSeller && handoff ? <button type="button" disabled={openHandoffMutation.isPending} onClick={() => openHandoffMutation.mutate()}>{openHandoffMutation.isPending ? "Opening…" : `Open ${handoff.recipient} payment page`}</button> : null}</> : null}
          </section>
        </div>
        {!isSeller ? <button className={styles.share} type="button" onClick={() => void copySellerLink()}><Copy /> Copy seller link</button> : null}
        {notice ? <StatusNotice
          tone={notice.tone}
          title={notice.tone === "error" ? "Action not completed" : "Done"}
          action={evidenceMutation.isError && isSeller && view.state === "REQUIREMENT_RELEASED"
            ? { label: evidenceMutation.isPending ? "Retrying…" : "Retry evidence submission", onAction: () => evidenceMutation.mutate(), disabled: evidenceMutation.isPending }
            : undefined}
        >{notice.text}</StatusNotice> : null}
      </> : null}
    </main>
  );
}
