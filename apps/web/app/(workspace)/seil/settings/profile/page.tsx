import type { Metadata } from "next";

import { ProfileSettingsModal } from "@/components/home/profile-preview";
import { CommerceWorkspace } from "@/components/workspace/commerce-workspace";

export const metadata: Metadata = { title: "SEIL settings" };

export default function SeilProfilePage() {
  return (
    <>
      <CommerceWorkspace initialMode="seil" initialContextTab="run" modeLocked />
      <ProfileSettingsModal workspace="seil" />
    </>
  );
}
