import type { Metadata } from "next";

import { SellerHome } from "@/components/seller/seller-surfaces";

export const metadata: Metadata = { title: "SEIL workspace" };

export default function SellerHomePage() {
  return <SellerHome />;
}
