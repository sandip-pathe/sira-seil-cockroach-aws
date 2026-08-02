import type { Metadata } from "next";

import { DecisionIndex } from "@/components/decisions/decision-surfaces";

export const metadata: Metadata = {
  title: "SIRA decisions",
  description: "Active and completed buying decisions in the SIRA workspace.",
};

export default function SiraDecisionsPage() {
  return <DecisionIndex />;
}
