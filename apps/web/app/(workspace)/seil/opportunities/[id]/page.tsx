import type { Metadata } from "next";

import { SellerOpportunity } from "@/components/qualification/qualified-marketplace";

export const metadata: Metadata = { title: "SEIL Opportunity" };

export default async function SeilOpportunityPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <SellerOpportunity engagementId={id} />;
}
