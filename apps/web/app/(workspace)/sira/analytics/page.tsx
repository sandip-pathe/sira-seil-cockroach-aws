import type { Metadata } from "next";

import { AnalyticsPage } from "@/components/home/analytics-page";

export const metadata: Metadata = { title: "SIRA analytics" };

export default function SiraAnalyticsPage() {
  return <AnalyticsPage workspace="sira" />;
}
