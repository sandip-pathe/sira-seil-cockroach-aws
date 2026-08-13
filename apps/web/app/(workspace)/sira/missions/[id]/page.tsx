import type { Metadata } from "next";

import { MissionRoom } from "@/components/qualification/qualified-marketplace";

export const metadata: Metadata = { title: "SIRA Mission" };

export default async function SiraMissionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <MissionRoom missionId={id} />;
}
