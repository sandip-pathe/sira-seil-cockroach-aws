import type { Metadata } from "next";

import { InboxPage } from "@/components/home/inbox-page";

export const metadata: Metadata = { title: "SIRA inbox" };

export default function SiraInboxPage() {
  return <InboxPage workspace="sira" />;
}
