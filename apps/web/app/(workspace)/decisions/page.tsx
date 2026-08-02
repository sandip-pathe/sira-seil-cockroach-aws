import type { Metadata } from "next";

import { DecisionIndex } from "@/components/decisions/decision-surfaces";

export const metadata: Metadata = { title: "Decisions" };

export default function DecisionsPage() {
  return <DecisionIndex />;
}
