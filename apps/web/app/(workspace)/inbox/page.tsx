import type { Metadata } from "next";

import { InboxPage } from "@/components/home/inbox-page";

export const metadata: Metadata = { title: "Inbox" };

export default function SharedInboxPage() {
  return <InboxPage />;
}
