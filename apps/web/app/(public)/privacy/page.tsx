import type { Metadata } from "next";

import { LegalPage } from "@/components/public/public-secondary-pages";

export const metadata: Metadata = { title: "Privacy" };

export default function Privacy() {
  return <LegalPage kind="privacy" />;
}
