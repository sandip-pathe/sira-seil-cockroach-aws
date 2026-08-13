import type { Metadata } from "next";

import { IntegrityRoom } from "@/components/qualification/qualified-marketplace";

export const metadata: Metadata = { title: "Mission Integrity" };

export default async function IntegrityPage({
  params,
}: {
  params: Promise<{ missionId: string }>;
}) {
  const { missionId } = await params;
  return <IntegrityRoom missionId={missionId} />;
}
