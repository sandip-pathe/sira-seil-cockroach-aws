import type { Metadata } from "next";

import { MarketplaceProduct } from "@/components/marketplace/marketplace";

export const metadata: Metadata = { title: "Published product evidence" };

export default async function MarketplaceProductPage({
  params,
}: {
  params: Promise<{ productId: string }>;
}) {
  const { productId } = await params;
  return <MarketplaceProduct productId={productId} />;
}
