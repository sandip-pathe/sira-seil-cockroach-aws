import type { Metadata } from "next";

import { SignInPreview } from "@/components/public/public-secondary-pages";

export const metadata: Metadata = {
  title: "SEIL sign in",
  description: "Sign in to the SEIL seller workspace.",
};

export default function SeilSignInPage() {
  return <SignInPreview preferredWorkspace="seil" />;
}
