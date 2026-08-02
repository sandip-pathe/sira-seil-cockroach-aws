import { ArrowLeft, LockKeyhole } from "lucide-react";
import Link from "next/link";

import { CombinedBrandLogo } from "@/components/brand/combined-brand-logo";

import styles from "./not-found.module.css";

export default function NotFound() {
  return (
    <main className={styles.page}>
      <Link className={styles.wordmark} href="/" aria-label="SIRA and SEIL home">
        <CombinedBrandLogo className={styles.combinedLogo} priority />
      </Link>
      <section>
        <LockKeyhole aria-hidden="true" />
        <p>Unavailable</p>
        <h1>This page cannot be shown.</h1>
        <span>The address may be incorrect, the record may no longer be current, or your authorized workspace may not include it. No private object details are exposed here.</span>
        <Link href="/"><ArrowLeft aria-hidden="true" /> Return to SIRA + SEIL home</Link>
      </section>
    </main>
  );
}
