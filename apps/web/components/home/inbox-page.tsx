"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, Clock3, Inbox, LockKeyhole } from "lucide-react";
import Link from "next/link";

import {
  WEB_DATA_MODE,
  buyerDevelopmentHeaders,
  getBrowserApiClient,
  sellerEditorDevelopmentHeaders,
} from "@/lib/api";

import styles from "./inbox-page.module.css";

type InboxWorkspace = "sira" | "seil";

const tasks = [
  {
    id: "review-decision",
    workspace: "SIRA",
    title: "Review the recommended meeting-intelligence action",
    meta: "Decision maker · due 19 Aug",
    href: "/decisions/req_demo/versions/1/options",
    tone: "sira",
  },
  {
    id: "confirm-authority",
    workspace: "SIRA",
    title: "Confirm approval roles before selection",
    meta: "Company fit · no payment requested",
    href: "/decisions/req_demo/versions/1/company-fit",
    tone: "sira",
  },
  {
    id: "pack-evidence",
    workspace: "SEIL",
    title: "Add current evidence for the retention claim",
    meta: "Seller editor · Pack has 1 evidence gap",
    href: "/seil/product-evidence/product_fixture_d",
    tone: "seil",
  },
] as const;

type InboxTask = {
  href: string;
  id: string;
  meta: string;
  title: string;
  tone: InboxWorkspace;
  workspace: string;
};

function useInbox(workspace: InboxWorkspace) {
  return useQuery({
    queryKey: ["qualification-inbox", workspace, WEB_DATA_MODE],
    queryFn: async (): Promise<InboxTask[]> => {
      if (WEB_DATA_MODE === "fixture") {
        return tasks.filter((task) => task.tone === workspace).map((task) => ({ ...task }));
      }
      const payload = await getBrowserApiClient().request("qualification_get_inbox", {
        headers: workspace === "sira" ? buyerDevelopmentHeaders : sellerEditorDevelopmentHeaders,
      });
      return payload.items.map((raw) => {
        const item = raw as Record<string, unknown>;
        return {
          href: String(item.href ?? `/${workspace}`),
          id: String(item.id),
          meta: `${String(item.state ?? "OPEN")} · ${item.requires_action ? "Needs action" : "Update"}`,
          title: String(item.title ?? "Marketplace update"),
          tone: workspace,
          workspace: workspace.toUpperCase(),
        };
      });
    },
  });
}

export function InboxPage({ workspace }: { workspace: InboxWorkspace }) {
  const workspaceName = workspace.toUpperCase();
  const inbox = useInbox(workspace);
  const workspaceTasks = inbox.data ?? [];

  return (
    <main className={styles.page} data-workspace={workspace}>
      <a className={styles.skipLink} href="#inbox-content">
        Skip to inbox
      </a>
      <header className={styles.header}>
        <Link href={`/${workspace}`} className={styles.wordmark}>
          {workspaceName}
        </Link>
        <nav aria-label="Account navigation">
          <Link href={`/${workspace}`}>Workspace</Link>
          <Link aria-current="page" href={`/${workspace}/inbox`}>
            Inbox
          </Link>
          <Link href={`/${workspace}/settings/profile`}>Profile</Link>
        </nav>
      </header>
      {WEB_DATA_MODE === "fixture" ? (
        <div className={styles.fixture}>
          <Clock3 aria-hidden="true" />
          <span>
            <strong>Development fixture</strong> — these tasks demonstrate the {workspaceName} queue
            and are not live notifications.
          </span>
        </div>
      ) : null}
      <div className={styles.content} id="inbox-content">
        <section className={styles.intro}>
          <div className={styles.inboxIcon}>
            <Inbox aria-hidden="true" />
          </div>
          <div>
            <p>{workspaceName} queue</p>
            <h1>Inbox</h1>
            <span>Only assignments and safe summaries for this workspace appear here.</span>
          </div>
        </section>
        <div className={styles.layout}>
          <section className={styles.taskList} aria-labelledby="needs-action">
            <div className={styles.sectionHead}>
              <div>
                <p>Needs action</p>
                <h2 id="needs-action">Assigned to you</h2>
              </div>
              <span>{workspaceTasks.length}</span>
            </div>
            {inbox.isPending ? (
              <div className={styles.emptyQueue} role="status">
                <Clock3 aria-hidden="true" />
                <div>
                  <strong>Loading current assignments</strong>
                  <span>Checking CockroachDB projections.</span>
                </div>
              </div>
            ) : inbox.isError ? (
              <div className={styles.emptyQueue} role="alert">
                <Clock3 aria-hidden="true" />
                <div>
                  <strong>Inbox unavailable</strong>
                  <span>No fixture task was substituted. Retry after the API is ready.</span>
                </div>
              </div>
            ) : workspaceTasks.length ? (
              workspaceTasks.map((task) => (
                <Link href={task.href} key={task.id} className={styles.task}>
                  <span className={styles.workspace} data-tone={task.tone}>
                    {task.workspace}
                  </span>
                  <span>
                    <strong>{task.title}</strong>
                    <small>{task.meta}</small>
                  </span>
                  <ArrowRight aria-hidden="true" />
                </Link>
              ))
            ) : (
              <div className={styles.emptyQueue}>
                <CheckCircle2 aria-hidden="true" />
                <div>
                  <strong>You are caught up</strong>
                  <span>New assignments and expiring actions will appear here.</span>
                </div>
              </div>
            )}
          </section>
          <aside className={styles.boundary}>
            <LockKeyhole aria-hidden="true" />
            <p>Notification boundary</p>
            <h2>Minimum safe context</h2>
            <ul>
              <li>
                <CheckCircle2 aria-hidden="true" /> Object and safe event label
              </li>
              <li>
                <CheckCircle2 aria-hidden="true" /> Required role and expiry
              </li>
              <li>
                <CheckCircle2 aria-hidden="true" /> Authenticated deep link
              </li>
            </ul>
            <span>
              Hidden company context, raw evidence, payment credentials, rejection detail, and
              pre-consent contacts never appear in notifications.
            </span>
          </aside>
        </div>
      </div>
    </main>
  );
}
