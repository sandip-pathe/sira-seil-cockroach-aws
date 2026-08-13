import type { Metadata } from "next";

import { AnalyticsPage } from "@/components/home/analytics-page";

export const metadata: Metadata = { title: "SEIL analytics" };

export default function SeilAnalyticsPage() {
  return <AnalyticsPage workspace="seil" />;
}
