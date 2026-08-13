import type { Metadata } from "next";

import { SellerProductWorkspace } from "@/components/seller/seller-surfaces";

export const metadata: Metadata = { title: "SEIL Product Evidence" };

export default async function SeilProductEvidencePage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ field?: string | string[] }>;
}) {
  const { id } = await params;
  const query = await searchParams;
  const field = Array.isArray(query.field) ? query.field[0] : query.field;
  return <SellerProductWorkspace productId={id} initialField={field} />;
}
