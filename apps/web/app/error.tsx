"use client";

import { CircleAlert, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useEffect } from "react";

import { CombinedBrandLogo } from "@/components/brand/combined-brand-logo";

import styles from "./not-found.module.css";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className={styles.page}>
      <Link className={styles.wordmark} href="/" aria-label="SIRA and SEIL home">
        <CombinedBrandLogo className={styles.combinedLogo} priority />
      </Link>
      <section>
        <CircleAlert aria-hidden="true" />
        <p>Could not load this screen</p>
        <h1>Your last confirmed work is unchanged.</h1>
        <span>Retry the screen. If it still fails, return home and reopen the correct SIRA or SEIL workspace.</span>
        <button type="button" onClick={reset}><RotateCcw aria-hidden="true" /> Retry this screen</button>
      </section>
    </main>
  );
}
