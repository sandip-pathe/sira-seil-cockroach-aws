import type { Metadata } from "next";

import { WorkspaceHome } from "@/components/home/workspace-home";

export const metadata: Metadata = { title: "Workspace home" };

export default function HomePage() {
  return (
    <WorkspaceHome
      displayName="Asha Singh"
      workspaces={[
        {
          id: "sira-northstar",
          kind: "sira",
          href: "/decisions",
          organizationName: "Northstar Advisory",
          statusLabel: "1 active decision",
          lastActivity: "Options evaluated 2 minutes ago",
        },
        {
          id: "seil-fixture-d",
          kind: "seil",
          href: "/seller",
          organizationName: "Meridian Software",
          statusLabel: "1 Pack needs attention",
          lastActivity: "Evidence updated today",
        },
      ]}
      recentWork={[
        {
          id: "decision-demo",
          workspace: "sira",
          title: "Meeting-intelligence renewal",
          meta: "Options ready · Decision v1",
          href: "/decisions/req_demo/versions/1/options",
        },
        {
          id: "product-demo",
          workspace: "seil",
          title: "Meridian Decisions Team",
          meta: "Product Evidence draft · 2 gaps",
          href: "/seller/product-evidence/product_fixture_d",
        },
      ]}
      assignedTasks={[
        {
          id: "task-review-options",
          workspace: "sira",
          title: "Review the recommended action",
          meta: "Decision maker · due 19 Aug",
          href: "/decisions/req_demo/versions/1/options",
        },
        {
          id: "task-pack-gap",
          workspace: "seil",
          title: "Add current retention evidence",
          meta: "Seller editor · Pack validation",
          href: "/seller/product-evidence/product_fixture_d",
        },
      ]}
      activationItems={[
        { id: "sira-first", workspace: "sira", label: "Run a guided first decision", complete: true, href: "/decisions" },
        { id: "sira-authority", workspace: "sira", label: "Confirm approval roles", complete: false, href: "/decisions/req_demo/versions/1/company-fit" },
        { id: "seil-claim", workspace: "seil", label: "Claim a product", complete: true, href: "/seller/products/search" },
        { id: "seil-publish", workspace: "seil", label: "Publish reviewed Product Evidence", complete: false, href: "/seller/product-evidence/product_fixture_d" },
      ]}
    />
  );
}
