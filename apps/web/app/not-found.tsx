import { ArrowLeft, LockKeyhole } from "lucide-react";
import Link from "next/link";

import styles from "./not-found.module.css";

export default function NotFound() {
  return (
    <main className={styles.page}>
      <Link className={styles.wordmark} href="/">SIRA <span>+</span> SEIL</Link>
      <section>
        <LockKeyhole aria-hidden="true" />
        <p>Unavailable</p>
        <h1>This page cannot be shown.</h1>
        <span>The address may be incorrect, the record may no longer be current, or your authorized workspace may not include it. No private object details are exposed here.</span>
        <Link href="/home"><ArrowLeft aria-hidden="true" /> Return to workspace home</Link>
      </section>
    </main>
  );
}
