import { SignInPreview } from "@/components/public/public-secondary-pages";

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
