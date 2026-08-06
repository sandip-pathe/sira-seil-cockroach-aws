import { notFound, redirect } from "next/navigation";

export default async function DecisionRoomPage({
  params,
}: {
  params: Promise<{ requestId: string; version: string; stage: string }>;
}) {
  const { requestId, version, stage } = await params;
  if (!["need", "company-fit", "options", "action", "result"].includes(stage)) {
    notFound();
  }
  redirect(`/sira?decision=${encodeURIComponent(requestId)}&version=${encodeURIComponent(version)}&stage=${encodeURIComponent(stage)}`);
}
