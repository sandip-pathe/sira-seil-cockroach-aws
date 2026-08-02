import type { Metadata } from "next";

import { NewDecision } from "@/components/decisions/decision-surfaces";

export const metadata: Metadata = { title: "New decision" };

export default function NewDecisionPage() {
  return <NewDecision />;
}
