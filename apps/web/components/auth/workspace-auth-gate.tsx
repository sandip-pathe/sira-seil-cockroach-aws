"use client";

import { LockKeyhole } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { useFirebaseAuth } from "./firebase-auth-provider";
import styles from "./workspace-auth-gate.module.css";

export function WorkspaceAuthGate({ children }: { children: ReactNode }) {
  const { configured, loading, user } = useFirebaseAuth();
  const pathname = usePathname();
  const router = useRouter();
  const developmentWorkspace = process.env.NODE_ENV === "development" && !configured;

  useEffect(() => {
    if (!configured || loading || user) return;
    const workspace = pathname.startsWith("/seil") || pathname.startsWith("/seller")
      ? "seil"
      : "sira";
    router.replace(`/sign-in?workspace=${workspace}`);
  }, [configured, loading, pathname, router, user]);

  if (developmentWorkspace || (configured && !loading && user)) return children;

  return (
    <main className={styles.gate}>
      <LockKeyhole aria-hidden="true" />
      <h1>{configured ? "Opening your workspace" : "Authentication setup required"}</h1>
      <p>
        {configured
          ? "Verifying your private workspace boundary."
          : "Firebase web credentials are missing from this build."}
      </p>
    </main>
  );
}
