import type { SellerProductSearchItem } from "@sira/api-client";

export type SellerEvidenceCard = {
  id: string;
  name: string;
  seller: string;
  edition: string;
  price: string;
  billing_unit: string;
  status: string;
  summary: string;
  claims: string[];
  integrations: string[];
  category?: string;
};

const AUTHORITY_LABELS: Record<SellerProductSearchItem["publisher_authority"], string> = {
  SELLER_SEALED: "Seller confirmed",
  PLATFORM_COMPILED: "Platform compiled",
  EXTERNAL_UNSEALED: "External source · unverified",
};

function stateLabel(state: SellerProductSearchItem["state"]): string {
  return state.toLowerCase().replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

/** Project only fields the seller search endpoint actually returns; absent commercial facts stay absent. */
export function adaptSellerProductSearchItem(item: SellerProductSearchItem): SellerEvidenceCard {
  const status = stateLabel(item.state);
  return {
    id: item.id,
    name: item.name,
    seller: AUTHORITY_LABELS[item.publisher_authority],
    edition: status,
    price: "Not provided",
    billing_unit: "pricing evidence",
    status,
    summary: item.public_summary,
    claims: [],
    integrations: [],
    category: item.category || undefined,
  };
}
