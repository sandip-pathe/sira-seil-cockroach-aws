import type { Metadata } from "next";

import { ProfileSettingsModal } from "@/components/home/profile-preview";
import { CommerceWorkspace } from "@/components/workspace/commerce-workspace";

export const metadata: Metadata = { title: "SIRA settings" };

export default function SiraProfilePage() {
  return (
    <>
      <CommerceWorkspace initialMode="sira" initialContextTab="run" modeLocked />
      <ProfileSettingsModal workspace="sira" />
    </>
  );
}
