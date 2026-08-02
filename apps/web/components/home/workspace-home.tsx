"use client";

import {
  ArrowRight,
  Building2,
  Check,
  Circle,
  Clock3,
  Inbox,
  ListChecks,
  PackageCheck,
  Settings,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, type RefObject } from "react";
import { layout, prepare, type PreparedText } from "@chenglou/pretext";

import { CombinedBrandLogo } from "@/components/brand/combined-brand-logo";

import styles from "./workspace-home.module.css";

export type WorkspaceKind = "sira" | "seil";

export type WorkspaceAccess = {
  id: string;
  kind: WorkspaceKind;
  href: string;
  organizationName: string;
  statusLabel?: string;
  lastActivity?: string;
};

export type WorkspaceHomeItem = {
  id: string;
  workspace: WorkspaceKind;
  title: string;
  meta: string;
  href: string;
};

export type ActivationItem = {
  id: string;
  workspace: WorkspaceKind;
  label: string;
  complete: boolean;
  href?: string;
};

export type WorkspaceHomeProps = {
  displayName?: string;
  workspaces: readonly WorkspaceAccess[];
  recentWork?: readonly WorkspaceHomeItem[];
  assignedTasks?: readonly WorkspaceHomeItem[];
  activationItems?: readonly ActivationItem[];
};

type PreparedElement = {
  element: HTMLElement;
  prepared: PreparedText;
  lineHeight: number;
};

function usePretextLayout(rootRef: RefObject<HTMLElement | null>, version: string) {
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;

    let cancelled = false;
    let observer: ResizeObserver | undefined;

    const start = async () => {
      await document.fonts.ready;
      if (cancelled) return;

      const entries: PreparedElement[] = Array.from(
        root.querySelectorAll<HTMLElement>("[data-pretext]"),
      ).map((element) => {
        const computed = getComputedStyle(element);
        const parsedLineHeight = Number.parseFloat(computed.lineHeight);
        const fontSize = Number.parseFloat(computed.fontSize);

        return {
          element,
          prepared: prepare(element.textContent ?? "", computed.font),
          lineHeight: Number.isFinite(parsedLineHeight)
            ? parsedLineHeight
            : fontSize * 1.4,
        };
      });

      const relayout = () => {
        for (const entry of entries) {
          const width = entry.element.getBoundingClientRect().width;
          if (width <= 0) continue;
          const result = layout(entry.prepared, width, entry.lineHeight);
          entry.element.style.setProperty(
            "--pretext-height",
            `${Math.ceil(result.height)}px`,
          );
        }
      };

      observer = new ResizeObserver(relayout);
      observer.observe(root);
      relayout();
    };

    void start();

    return () => {
      cancelled = true;
      observer?.disconnect();
    };
  }, [rootRef, version]);
}

const workspaceContent = {
  sira: {
    name: "SIRA",
    label: "Buyer workspace",
    description:
      "Build a Purchase Brief, compare supported actions, route exact authority, and verify the result.",
    action: "Enter SIRA",
    icon: Building2,
  },
  seil: {
    name: "SEIL",
    label: "Seller workspace",
    description:
      "Maintain private product knowledge, publish reviewed Product Evidence, and respond to qualified requirements.",
    action: "Enter SEIL",
    icon: PackageCheck,
  },
} as const;

function WorkspaceTag({ workspace }: { workspace: WorkspaceKind }) {
  return (
    <span className={styles.workspaceTag} data-workspace={workspace}>
      {workspace.toUpperCase()}
    </span>
  );
}

function WorkList({
  items,
  emptyText,
}: {
  items: readonly WorkspaceHomeItem[];
  emptyText: string;
}) {
  if (items.length === 0) {
    return <p className={styles.emptyList}>{emptyText}</p>;
  }

  return (
    <ul className={styles.workList}>
      {items.map((item) => (
        <li key={item.id}>
          <Link href={item.href}>
            <div>
              <WorkspaceTag workspace={item.workspace} />
              <strong>{item.title}</strong>
              <span>{item.meta}</span>
            </div>
            <ArrowRight aria-hidden="true" />
          </Link>
        </li>
      ))}
    </ul>
  );
}

export function WorkspaceHome({
  displayName,
  workspaces,
  recentWork = [],
  assignedTasks = [],
  activationItems = [],
}: WorkspaceHomeProps) {
  const pageRef = useRef<HTMLElement>(null);
  const organizationNames = useMemo(
    () => Array.from(new Set(workspaces.map((workspace) => workspace.organizationName))),
    [workspaces],
  );
  const layoutVersion = useMemo(
    () =>
      [
        displayName ?? "",
        ...workspaces.map((workspace) => `${workspace.id}:${workspace.statusLabel ?? ""}`),
        ...recentWork.map((item) => item.id),
        ...assignedTasks.map((item) => item.id),
        ...activationItems.map((item) => `${item.id}:${item.complete}`),
      ].join("|"),
    [activationItems, assignedTasks, displayName, recentWork, workspaces],
  );
  usePretextLayout(pageRef, layoutVersion);

  const completeActivationCount = activationItems.filter((item) => item.complete).length;

  return (
    <main className={styles.page} ref={pageRef}>
      <a className={styles.skipLink} href="#workspace-content">
        Skip to workspaces
      </a>

      <header className={styles.header}>
        <div className={styles.headerInner}>
          <Link className={styles.wordmark} href="/home" aria-label="SIRA and SEIL home">
            <CombinedBrandLogo className={styles.combinedLogo} />
          </Link>
          <div className={styles.accountSummary}>
            <span>{displayName ? `Signed in as ${displayName}` : "Signed in"}</span>
            <Link href="/settings/profile">
              <Settings aria-hidden="true" /> Profile
            </Link>
          </div>
        </div>
      </header>

      <div className={styles.content} id="workspace-content">
        <section className={styles.intro} aria-labelledby="workspace-home-title">
          <div>
            <p className={styles.eyebrow}>Workspace home</p>
            <h1 id="workspace-home-title" data-pretext>
              {displayName ? `Where are you working today, ${displayName}?` : "Where are you working today?"}
            </h1>
            <p data-pretext>
              Choose an authorized workspace. The product, organization, navigation,
              and vocabulary change with it. Your role and access do not.
            </p>
          </div>

          <aside className={styles.organizationSummary} aria-label="Authorized organizations">
            <span>Organizations</span>
            {organizationNames.length > 0 ? (
              <ul>
                {organizationNames.map((name) => <li key={name}>{name}</li>)}
              </ul>
            ) : (
              <p>No organization access</p>
            )}
          </aside>
        </section>

        <section className={styles.workspaceSection} aria-labelledby="available-workspaces-title">
          <div className={styles.sectionHeader}>
            <div>
              <p>Available to you</p>
              <h2 id="available-workspaces-title">Choose a workspace</h2>
            </div>
            <span>{workspaces.length} {workspaces.length === 1 ? "workspace" : "workspaces"}</span>
          </div>

          {workspaces.length > 0 ? (
            <div className={styles.workspaceGrid}>
              {workspaces.map((workspace) => {
                const content = workspaceContent[workspace.kind];
                const Icon = content.icon;

                return (
                  <article
                    className={styles.workspaceCard}
                    data-workspace={workspace.kind}
                    key={workspace.id}
                  >
                    <div className={styles.cardTopline}>
                      <span><Icon aria-hidden="true" /> {content.label}</span>
                      {workspace.statusLabel ? <small>{workspace.statusLabel}</small> : null}
                    </div>
                    <h3>{content.name}</h3>
                    <p data-pretext>{content.description}</p>
                    <dl>
                      <div>
                        <dt>Organization</dt>
                        <dd>{workspace.organizationName}</dd>
                      </div>
                      {workspace.lastActivity ? (
                        <div>
                          <dt>Last activity</dt>
                          <dd>{workspace.lastActivity}</dd>
                        </div>
                      ) : null}
                    </dl>
                    <Link href={workspace.href}>
                      {content.action} <ArrowRight aria-hidden="true" />
                    </Link>
                  </article>
                );
              })}
            </div>
          ) : (
            <div className={styles.noWorkspace} role="status">
              <ShieldCheck aria-hidden="true" />
              <div>
                <h3>No workspace access yet</h3>
                <p>Ask an organization administrator to invite you to a SIRA or SEIL workspace.</p>
              </div>
            </div>
          )}
        </section>

        <section className={styles.activitySection} aria-label="Recent work and assignments">
          <div className={styles.recentPanel}>
            <div className={styles.panelHeader}>
              <span><Clock3 aria-hidden="true" /> Continue your work</span>
              <strong>{recentWork.length}</strong>
            </div>
            <WorkList
              items={recentWork}
              emptyText="Your latest authorized Decisions and Products will appear here."
            />
          </div>

          <div className={styles.sidePanels}>
            <div className={styles.taskPanel}>
              <div className={styles.panelHeader}>
                <span><Inbox aria-hidden="true" /> Assigned to you</span>
                <strong>{assignedTasks.length}</strong>
              </div>
              <WorkList
                items={assignedTasks}
                emptyText="No approvals, evidence requests, reviews, or execution tasks need you now."
              />
            </div>

            <div className={styles.activationPanel}>
              <div className={styles.panelHeader}>
                <span><ListChecks aria-hidden="true" /> Activation checklist</span>
                <strong>{completeActivationCount}/{activationItems.length}</strong>
              </div>
              {activationItems.length > 0 ? (
                <ul className={styles.activationList}>
                  {activationItems.map((item) => {
                    const body = (
                      <>
                        {item.complete ? <Check aria-hidden="true" /> : <Circle aria-hidden="true" />}
                        <WorkspaceTag workspace={item.workspace} />
                        <span>{item.label}</span>
                      </>
                    );

                    return (
                      <li className={item.complete ? styles.completeItem : undefined} key={item.id}>
                        {item.href ? <Link href={item.href}>{body}</Link> : <div>{body}</div>}
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className={styles.emptyList}>No setup steps are required for your current access.</p>
              )}
            </div>
          </div>
        </section>

        <footer className={styles.boundaryNote}>
          <ShieldCheck aria-hidden="true" />
          <p>
            Workspace access is filtered by the server. Switching changes the visible
            product and organization boundary; it never grants a role or permission.
          </p>
        </footer>
      </div>
    </main>
  );
}
