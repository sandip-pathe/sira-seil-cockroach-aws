import type { Metadata } from "next";

import { SignInPreview } from "@/components/public/public-secondary-pages";

export const metadata: Metadata = {
  title: "SIRA sign in",
  description: "Sign in to the SIRA buyer workspace.",
};

export default function SiraSignInPage() {
  return <SignInPreview preferredWorkspace="sira" />;
}
