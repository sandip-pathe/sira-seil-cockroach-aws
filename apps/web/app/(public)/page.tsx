import type { Metadata } from "next";

import { LandingPage } from "@/components/public/landing-page";

export const metadata: Metadata = {
  title: { absolute: "SIRA + SEIL" },
  description: "Choose SIRA for buying decisions or SEIL for trusted B2B product evidence.",
};

export default function PublicLandingPage() {
  return <LandingPage />;
}
