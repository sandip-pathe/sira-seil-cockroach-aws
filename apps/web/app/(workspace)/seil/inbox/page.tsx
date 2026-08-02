import type { Metadata } from "next";

import { InboxPage } from "@/components/home/inbox-page";

export const metadata: Metadata = { title: "SEIL inbox" };

export default function SeilInboxPage() {
  return <InboxPage workspace="seil" />;
}
