import { SiraApiClient } from "@sira/api-client";

export type WebDataMode = "fixture" | "api";

const configuredDataMode = process.env.NEXT_PUBLIC_WEB_DATA_MODE;

if (
  configuredDataMode !== undefined &&
  configuredDataMode !== "fixture" &&
  configuredDataMode !== "api"
) {
  throw new Error(
    "NEXT_PUBLIC_WEB_DATA_MODE must be either 'fixture' or 'api'; refusing an implicit fallback.",
  );
}

export const WEB_DATA_MODE: WebDataMode =
  configuredDataMode ?? (process.env.NODE_ENV === "production" ? "api" : "fixture");

const developmentIdentityEnabled = process.env.NEXT_PUBLIC_DEVELOPMENT_IDENTITY === "true";
const noDevelopmentHeaders = Object.freeze({}) as Readonly<Record<string, string>>;

function developmentHeaders(
  actorId: string,
  actorParty: "BUYER" | "SELLER",
  actorRoles: string,
): Readonly<Record<string, string>> {
  if (!developmentIdentityEnabled) return noDevelopmentHeaders;

  return Object.freeze({
    "X-Organization-Id": "org_consultco",
    "X-Actor-Id": actorId,
    "X-Actor-Party": actorParty,
    "X-Actor-Roles": actorRoles,
    "X-Step-Up-Verified": "true",
    "X-Identity-Kind": "HUMAN",
  });
}

export const buyerDevelopmentHeaders = developmentHeaders(
  "usr_demo_requester",
  "BUYER",
  [
    "can_submit_request",
    "can_view_context",
    "can_select_recommendation",
    "can_manage_procurement_gate",
    "can_approve_purchase",
    "can_execute_purchase",
  ].join(","),
);

export const sellerEditorDevelopmentHeaders = developmentHeaders(
  "seller_fixture_d",
  "SELLER",
  "seller_editor",
);

export const sellerReviewerDevelopmentHeaders = developmentHeaders(
  "seller_reviewer_fixture_d",
  "SELLER",
  "seller_reviewer",
);

let browserApiClient: SiraApiClient | undefined;

export function getBrowserApiClient(): SiraApiClient {
  if (typeof window === "undefined") {
    throw new Error("getBrowserApiClient() is only available in the browser.");
  }

  browserApiClient ??= new SiraApiClient(window.location.origin);
  return browserApiClient;
}

/** Create once when a user starts an action, then reuse the value for every retry of it. */
export function createIdempotencyKey(scope: string): string {
  const normalizedScope = scope
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);

  return `${normalizedScope || "web-action"}-${globalThis.crypto.randomUUID()}`;
}
