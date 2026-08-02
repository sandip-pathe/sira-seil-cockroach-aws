"use client";

import { ArrowRight, CheckCircle2, Clock3, Inbox, LockKeyhole } from "lucide-react";
import Link from "next/link";

import { WEB_DATA_MODE } from "@/lib/api";

import styles from "./inbox-page.module.css";

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
    meta: "Seller editor · Pack has 2 validation gaps",
    href: "/seller/product-evidence/product_fixture_d",
    tone: "seil",
  },
] as const;

export function InboxPage() {
  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <Link href="/home" className={styles.wordmark}>SIRA <span>+</span> SEIL</Link>
        <nav aria-label="Account navigation"><Link href="/home">Workspace home</Link><Link href="/settings/profile">Profile</Link></nav>
      </header>
      {WEB_DATA_MODE === "fixture" ? <div className={styles.fixture}><Clock3 aria-hidden="true" /><span><strong>Development fixture</strong> — these tasks demonstrate the shared queue and are not live notifications.</span></div> : null}
      <div className={styles.content}>
        <section className={styles.intro}>
          <div className={styles.inboxIcon}><Inbox aria-hidden="true" /></div>
          <div><p>Shared queue</p><h1>Inbox</h1><span>Only assignments and safe summaries authorized for the current workspace appear here.</span></div>
        </section>
        <div className={styles.layout}>
          <section className={styles.taskList} aria-labelledby="needs-action">
            <div className={styles.sectionHead}><div><p>Needs action</p><h2 id="needs-action">Assigned to you</h2></div><span>{tasks.length}</span></div>
            {tasks.map((task) => <Link href={task.href} key={task.id} className={styles.task}><span className={styles.workspace} data-tone={task.tone}>{task.workspace}</span><span><strong>{task.title}</strong><small>{task.meta}</small></span><ArrowRight aria-hidden="true" /></Link>)}
          </section>
          <aside className={styles.boundary}>
            <LockKeyhole aria-hidden="true" />
            <p>Notification boundary</p>
            <h2>Minimum safe context</h2>
            <ul><li><CheckCircle2 aria-hidden="true" /> Object and safe event label</li><li><CheckCircle2 aria-hidden="true" /> Required role and expiry</li><li><CheckCircle2 aria-hidden="true" /> Authenticated deep link</li></ul>
            <span>Hidden company context, raw evidence, payment credentials, rejection detail, and pre-consent contacts never appear in notifications.</span>
          </aside>
        </div>
      </div>
    </main>
  );
}
