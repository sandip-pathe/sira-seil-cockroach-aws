import type { Metadata } from "next";

import { SellerProductSearch } from "@/components/seller/seller-surfaces";

export const metadata: Metadata = { title: "SEIL products" };

export default function SeilProductSearchPage() {
  return <SellerProductSearch />;
}
