import type { Metadata } from "next";

import { SecurityPage } from "@/components/public/public-secondary-pages";

export const metadata: Metadata = {
  title: "Security",
  description: "Security, privacy boundaries, evidence authority, and payment separation in SIRA and SEIL.",
};

export default function Security() {
  return <SecurityPage />;
}
