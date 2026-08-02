import { redirect } from "next/navigation";

export default async function SellerProductEvidencePage({
  params,
  searchParams,
}: {
  params: Promise<{ productId: string }>;
  searchParams: Promise<{ field?: string | string[] }>;
}) {
  const { productId } = await params;
  const query = await searchParams;
  const field = Array.isArray(query.field) ? query.field[0] : query.field;
  redirect(`/seil/product-evidence/${productId}${field ? `?field=${encodeURIComponent(field)}` : ""}`);
}
