import type { Metadata } from "next";

import { SellerProductSearch } from "@/components/seller/seller-surfaces";

export const metadata: Metadata = { title: "Find a product" };

export default function SellerProductSearchPage() {
  return <SellerProductSearch />;
}
