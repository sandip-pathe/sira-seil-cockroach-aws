import type { Metadata } from "next";

import { ExchangeRoom } from "@/components/exchange/exchange-room";

export const metadata: Metadata = {
  title: "Governed seller exchange",
  description: "Negotiate exact B2B terms without mixing buyer and seller private context.",
};

export default async function ExchangePage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  return <ExchangeRoom caseId={caseId} />;
}
