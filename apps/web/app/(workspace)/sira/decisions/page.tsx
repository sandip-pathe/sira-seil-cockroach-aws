import type { Metadata } from "next";

import { DecisionIndex } from "@/components/decisions/decision-surfaces";

export const metadata: Metadata = {
  title: "Decisions",
  description: "Review active and historical SIRA buying decisions.",
};

export default function SiraDecisionsPage() {
  return <DecisionIndex />;
}
