import type { ReactNode } from "react";

import { WorkspaceAuthGate } from "@/components/auth/workspace-auth-gate";

export default function WorkspaceLayout({ children }: { children: ReactNode }) {
  return <WorkspaceAuthGate>{children}</WorkspaceAuthGate>;
}
