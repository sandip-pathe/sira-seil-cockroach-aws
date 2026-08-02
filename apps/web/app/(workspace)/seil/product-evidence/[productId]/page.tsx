import type { Metadata } from "next";

import { SellerProductWorkspace } from "@/components/seller/seller-surfaces";

export const metadata: Metadata = { title: "SEIL Product Evidence" };

export default async function SeilProductEvidencePage({
  params,
  searchParams,
}: {
  params: Promise<{ productId: string }>;
  searchParams: Promise<{ field?: string | string[] }>;
}) {
  const { productId } = await params;
  const query = await searchParams;
  const initialField = Array.isArray(query.field) ? query.field[0] : query.field;
  return <SellerProductWorkspace productId={productId} initialField={initialField} />;
}
