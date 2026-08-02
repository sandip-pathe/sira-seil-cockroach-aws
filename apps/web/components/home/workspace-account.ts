export type ProfileWorkspace = "sira" | "seil";

export const WORKSPACE_ACCOUNTS = {
  sira: {
    boundary:
      "Private to your company. Decision, approval, and payment authority remain separate from this profile.",
    email: "asha@example.invalid",
    initials: "AS",
    name: "Asha Singh",
    organization: "Northstar Advisory",
    role: "Decision maker preview",
    roleShort: "Decision maker",
    scope: "Buyer workspace",
  },
  seil: {
    boundary:
      "Private to your seller workspace. Only reviewed fields can become published Product Evidence.",
    email: "priya@example.invalid",
    initials: "PR",
    name: "Priya Rao",
    organization: "Seller workspace",
    role: "Seller editor preview",
    roleShort: "Seller editor",
    scope: "Seller workspace",
  },
} as const satisfies Record<
  ProfileWorkspace,
  {
    boundary: string;
    email: string;
    initials: string;
    name: string;
    organization: string;
    role: string;
    roleShort: string;
    scope: string;
  }
>;
