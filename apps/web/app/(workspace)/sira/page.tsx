import type { Metadata } from "next";

import { CommerceWorkspace } from "@/components/workspace/commerce-workspace";

export const metadata: Metadata = {
  title: "Talk to SIRA",
  description: "Work privately with SIRA on B2B buying decisions.",
};

export default function SiraPage() {
  return <CommerceWorkspace initialMode="sira" initialContextTab="decisions" modeLocked />;
}
