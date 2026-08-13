import { redirect } from "next/navigation";

function configuredWorkspace(): string {
  const value = process.env.NEXT_PUBLIC_PAYMENT_WORKSPACE_URL?.trim();
  if (!value) return "/payment";
  try {
    const target = new URL(value);
    return target.protocol === "https:" ? target.toString() : "/payment";
  } catch {
    return "/payment";
  }
}

export default function OpenPaymentWorkspacePage() {
  redirect(configuredWorkspace());
}
