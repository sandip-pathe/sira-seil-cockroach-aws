import type { Metadata } from "next";

import { QualificationHome } from "@/components/qualification/qualified-marketplace";

export const metadata: Metadata = {
  title: "SIRA Qualified Marketplace",
  description: "Start a durable B2B buying mission with SIRA.",
};

export default function SiraPage() {
  return <QualificationHome />;
}
