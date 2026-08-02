import type { Metadata } from "next";

import { SellerProductWorkspace } from "@/components/seller/seller-surfaces";

export const metadata: Metadata = { title: "Product Evidence" };

export default async function SellerProductEvidencePage({
  params,
}: {
  params: Promise<{ productId: string }>;
}) {
  const { productId } = await params;
  return <SellerProductWorkspace productId={productId} />;
}
