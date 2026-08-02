import type { Metadata } from "next";

import { LegalPage } from "@/components/public/public-secondary-pages";

export const metadata: Metadata = { title: "Terms" };

export default function Terms() {
  return <LegalPage kind="terms" />;
}
