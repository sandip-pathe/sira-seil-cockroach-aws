import type { Metadata } from "next";

import { MatchRoom } from "@/components/qualification/qualified-marketplace";

export const metadata: Metadata = { title: "Qualified Match" };

export default async function MatchPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <MatchRoom engagementId={id} />;
}
