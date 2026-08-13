import { SiraApiClient } from "@sira/api-client";

import { firebaseConfigured, getFirebaseAuth } from "@/lib/firebase";

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

function guestWorkspaceHeaders(mode: "sira" | "seil"): Readonly<Record<string, string>> {
  const developmentIdentity: Record<string, string> = mode === "sira"
    ? {
        "X-Actor-Party": "BUYER",
        "X-Actor-Roles": [
          "can_submit_request",
          "can_view_context",
          "can_select_recommendation",
          "can_manage_procurement_gate",
          "can_approve_purchase",
          "can_execute_purchase",
        ].join(","),
        "X-Step-Up-Verified": "true",
      }
    : {
        "X-Actor-Party": "SELLER",
        "X-Actor-Roles": "seller_editor,can_view_context",
      };
  return Object.freeze({ "X-Workspace-Mode": mode, ...developmentIdentity });
}

export const buyerDevelopmentHeaders = guestWorkspaceHeaders("sira");
export const sellerEditorDevelopmentHeaders = guestWorkspaceHeaders("seil");
export const sellerReviewerDevelopmentHeaders = guestWorkspaceHeaders("seil");

let browserApiClient: SiraApiClient | undefined;

const authenticatedFetch: typeof fetch = async (input, init) => {
  const headers = new Headers(init?.headers);
  if (firebaseConfigured) {
    const auth = getFirebaseAuth();
    await auth.authStateReady();
    const token = await auth.currentUser?.getIdToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  return fetch(input, { ...init, credentials: "same-origin", headers });
};

export function getBrowserApiClient(): SiraApiClient {
  if (typeof window === "undefined") {
    throw new Error("getBrowserApiClient() is only available in the browser.");
  }

  browserApiClient ??= new SiraApiClient(window.location.origin, authenticatedFetch);
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
