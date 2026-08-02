import type { Metadata } from "next";

import { PricingPage } from "@/components/public/public-secondary-pages";

export const metadata: Metadata = {
  title: "Pricing",
  description: "How SIRA and SEIL separate product access, transactions, and ranking.",
};

export default function Pricing() {
  return <PricingPage />;
}
