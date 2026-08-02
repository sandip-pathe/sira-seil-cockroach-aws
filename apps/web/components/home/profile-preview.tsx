import { ArrowLeft, Bell, CircleAlert, Languages, MoonStar, UserRound } from "lucide-react";
import Link from "next/link";

import styles from "./profile-preview.module.css";

export function ProfilePreview() {
  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <Link className={styles.wordmark} href="/home">SIRA <span>+</span> SEIL</Link>
        <nav aria-label="Account navigation">
          <Link href="/inbox">Inbox</Link>
          <Link aria-current="page" href="/settings/profile">Profile</Link>
        </nav>
      </header>

      <div className={styles.notice} role="status">
        <CircleAlert aria-hidden="true" />
        <span><strong>Development preview.</strong> Identity and notification settings are read-only until authentication is connected.</span>
      </div>

      <section className={styles.content} aria-labelledby="profile-title">
        <Link className={styles.back} href="/home"><ArrowLeft aria-hidden="true" /> Workspace home</Link>
        <div className={styles.heading}>
          <p>Personal settings</p>
          <h1 id="profile-title">Profile and notifications</h1>
          <span>These preferences follow you across every organization and authorized workspace.</span>
        </div>

        <div className={styles.settingsGrid}>
          <article>
            <div className={styles.sectionTitle}><UserRound aria-hidden="true" /><div><small>Profile</small><h2>Asha Singh</h2></div></div>
            <dl>
              <div><dt>Work email</dt><dd>asha@example.invalid</dd></div>
              <div><dt>Authorized workspace</dt><dd>Development fixture only</dd></div>
            </dl>
          </article>

          <article>
            <div className={styles.sectionTitle}><Languages aria-hidden="true" /><div><small>Locale</small><h2>Language and region</h2></div></div>
            <dl>
              <div><dt>Language</dt><dd>English</dd></div>
              <div><dt>Region and time</dt><dd>India · Asia/Calcutta</dd></div>
            </dl>
          </article>

          <article>
            <div className={styles.sectionTitle}><Bell aria-hidden="true" /><div><small>Notifications</small><h2>Safe task summaries</h2></div></div>
            <dl>
              <div><dt>In-app inbox</dt><dd>Canonical</dd></div>
              <div><dt>Email assignments</dt><dd>Not connected</dd></div>
              <div><dt>Slack or Teams</dt><dd>Not connected</dd></div>
            </dl>
          </article>

          <article>
            <div className={styles.sectionTitle}><MoonStar aria-hidden="true" /><div><small>Accessibility</small><h2>Display and quiet hours</h2></div></div>
            <dl>
              <div><dt>Theme</dt><dd>Light</dd></div>
              <div><dt>Quiet hours</dt><dd>Not configured</dd></div>
            </dl>
          </article>
        </div>

        <p className={styles.safetyNote}>No settings were saved, and this screen does not grant an organization role or change notification delivery.</p>
      </section>
    </main>
  );
}
