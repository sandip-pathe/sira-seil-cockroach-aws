import type { Metadata } from "next";

import { CommerceWorkspace } from "@/components/workspace/commerce-workspace";

export const metadata: Metadata = {
  title: "Talk to SIRA",
  description: "Work privately with SIRA on B2B buying decisions.",
};

export default async function SiraPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const requestId = typeof params.decision === "string" ? params.decision : null;
  const versionValue = typeof params.version === "string" ? Number(params.version) : 1;
  const stageValue = typeof params.stage === "string" ? params.stage : "options";
  const validStage = ["need", "company-fit", "options", "action", "result"].includes(stageValue)
    ? stageValue
    : "options";
  const initialDecision = requestId && Number.isInteger(versionValue) && versionValue > 0
    ? { requestId, version: versionValue, stage: validStage }
    : null;

  return (
    <CommerceWorkspace
      initialMode="sira"
      initialContextTab="decisions"
      initialContextOpen={params.panel === "decisions"}
      initialDecision={initialDecision}
      modeLocked
    />
  );
}
