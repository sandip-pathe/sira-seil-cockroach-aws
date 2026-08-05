"use client";

import { useEffect, useState } from "react";

import { buyerDevelopmentHeaders, getBrowserApiClient } from "@/lib/api";

export default function PravaReturnPage() {
  const [message, setMessage] = useState("Confirming Prava authorization…");

  useEffect(() => {
    const search = new URLSearchParams(window.location.search);
    const state = search.get("state");
    const returnUrl = search.get("return_url");
    if (!state || !returnUrl) {
      queueMicrotask(() => setMessage("This Prava return link is incomplete."));
      return;
    }
    void getBrowserApiClient()
      .request("accept_prava_browser_return_v2", {
        headers: buyerDevelopmentHeaders,
        query: { state, return_url: returnUrl },
      })
      .then(() => window.location.replace(returnUrl))
      .catch(() => setMessage("Prava authorization could not be confirmed. Return to SIRA and retry."));
  }, []);

  return (
    <main style={{ display: "grid", minHeight: "100vh", placeItems: "center", padding: "2rem" }}>
      <p role="status">{message}</p>
    </main>
  );
}
