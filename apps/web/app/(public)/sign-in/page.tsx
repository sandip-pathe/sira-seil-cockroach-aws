import type { Metadata } from "next";

import { SignInPreview } from "@/components/public/public-secondary-pages";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Choose the separate SIRA buyer or SEIL seller sign-in entry.",
};

type PageProps = {
  searchParams: Promise<{ workspace?: string | string[] }>;
};

export default async function SignInPage({ searchParams }: PageProps) {
  const params = await searchParams;
  const requested = Array.isArray(params.workspace)
    ? params.workspace[0]
    : params.workspace;
  const preferredWorkspace = requested === "sira" || requested === "seil"
    ? requested
    : undefined;

  return <SignInPreview preferredWorkspace={preferredWorkspace} />;
}
