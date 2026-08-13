import type { Metadata } from "next";

import { MarketplaceSearch } from "@/components/marketplace/marketplace";

export const metadata: Metadata = { title: "Evidence marketplace" };

export default function MarketplacePage() {
  return <MarketplaceSearch />;
}
