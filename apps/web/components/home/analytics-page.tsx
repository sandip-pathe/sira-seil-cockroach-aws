"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, ArrowLeft, BarChart3, Database, ShieldCheck } from "lucide-react";
import Link from "next/link";

import {
  WEB_DATA_MODE,
  buyerDevelopmentHeaders,
  getBrowserApiClient,
  sellerEditorDevelopmentHeaders,
} from "@/lib/api";

import styles from "./analytics-page.module.css";

type AnalyticsWorkspace = "sira" | "seil";

function label(value: string): string {
  return value.replaceAll("_", " ").toLowerCase();
}

export function AnalyticsPage({ workspace }: { workspace: AnalyticsWorkspace }) {
  const analytics = useQuery({
    queryKey: ["workspace-analytics", workspace, WEB_DATA_MODE],
    enabled: WEB_DATA_MODE === "api",
    queryFn: () =>
      getBrowserApiClient().request("qualification_get_workspace_analytics", {
        headers: workspace === "sira" ? buyerDevelopmentHeaders : sellerEditorDevelopmentHeaders,
      }),
  });
  const workspaceName = workspace.toUpperCase();
  const data = analytics.data;

  return (
    <main className={styles.page} data-workspace={workspace}>
      <header className={styles.header}>
        <Link href={`/${workspace}`}>
          <ArrowLeft aria-hidden="true" /> {workspaceName}
        </Link>
        <span>
          <Database aria-hidden="true" /> CockroachDB operating view
        </span>
      </header>
      <section className={styles.hero}>
        <div>
          <p>Marketplace operations</p>
          <h1>{workspaceName} activity</h1>
          <span>
            Tenant-private counts derived from canonical records and the transactional outbox.
          </span>
        </div>
        <BarChart3 aria-hidden="true" />
      </section>
      {WEB_DATA_MODE === "fixture" ? (
        <div className={styles.notice}>
          Analytics is intentionally unavailable in fixture mode; no synthetic metrics are
          substituted.
        </div>
      ) : null}
      {analytics.isPending && WEB_DATA_MODE === "api" ? (
        <div className={styles.loading} aria-label="Loading analytics">
          <i />
          <i />
          <i />
        </div>
      ) : null}
      {analytics.isError ? (
        <div className={styles.notice} role="alert">
          Current analytics could not be loaded. No cached or cross-tenant values were substituted.
        </div>
      ) : null}
      {data ? (
        <>
          <section className={styles.cards} aria-label="Marketplace funnel">
            {Object.entries(data.funnel).map(([name, value]) => (
              <article key={name}>
                <Activity aria-hidden="true" />
                <strong>{value}</strong>
                <span>{label(name)}</span>
              </article>
            ))}
          </section>
          <section className={styles.grid}>
            <article className={styles.panel}>
              <p>Current state</p>
              <h2>Work requiring attention</h2>
              <dl>
                {Object.entries(data.current_state).map(([name, value]) => (
                  <div key={name}>
                    <dt>{label(name)}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
            </article>
            <article className={styles.panel}>
              <p>Event volume</p>
              <h2>Last {data.window_days} days</h2>
              {data.daily_events.length ? (
                <ol>
                  {data.daily_events.map((item) => (
                    <li key={String(item.date)}>
                      <span>{String(item.date)}</span>
                      <strong>{Number(item.count)}</strong>
                    </li>
                  ))}
                </ol>
              ) : (
                <div className={styles.empty}>No canonical events in this window.</div>
              )}
            </article>
          </section>
          <footer className={styles.boundary}>
            <ShieldCheck aria-hidden="true" />
            <div>
              <strong>Observational, not causal</strong>
              <span>
                These counts do not expose buyer context, seller evidence, contacts, model prompts,
                or claim business impact. RLS applies before aggregation.
              </span>
            </div>
          </footer>
        </>
      ) : null}
    </main>
  );
}
