import type { Metadata } from "next";

import { ProofWorkspace } from "@/components/proof/proof-workspace";

export const metadata: Metadata = {
  title: "SIRA Proof of Fit",
  description:
    "Verify a seller release against live DataHub context and inspect the resulting receipt.",
};

export default function ProofPage() {
  return <ProofWorkspace />;
}
