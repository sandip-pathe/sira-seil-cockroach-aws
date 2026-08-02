import type { Metadata } from "next";

import { DecisionRoom } from "@/components/decisions/decision-surfaces";

export const metadata: Metadata = { title: "Decision Room" };

export default async function DecisionRoomPage({
  params,
}: {
  params: Promise<{ requestId: string; version: string; stage: string }>;
}) {
  const { requestId, version, stage } = await params;
  return <DecisionRoom requestId={requestId} version={version} stage={stage} />;
}
