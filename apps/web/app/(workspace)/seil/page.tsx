import type { Metadata } from "next";

import { CommerceWorkspace } from "@/components/workspace/commerce-workspace";

export const metadata: Metadata = {
  title: "Talk to SEIL",
  description: "Work privately with SEIL on B2B product evidence and selling.",
};

export default function SeilPage() {
  return <CommerceWorkspace initialMode="seil" initialContextTab="catalog" modeLocked />;
}
