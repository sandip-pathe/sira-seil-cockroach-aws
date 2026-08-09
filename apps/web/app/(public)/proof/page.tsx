import type { Metadata } from "next";

import { ProofWorkspace } from "@/components/proof/proof-workspace";

export const metadata: Metadata = {
  title: "SIRA Proof of Fit",
  description: "Operate and inspect the DataHub-causal software proof.",
};

export default function PublicProofPage() {
  return <ProofWorkspace />;
}
