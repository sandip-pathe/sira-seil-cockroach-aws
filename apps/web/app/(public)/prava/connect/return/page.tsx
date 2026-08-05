"use client";

import { useEffect, useState } from "react";

import { buyerDevelopmentHeaders } from "@/lib/api";

export default function PravaConnectReturnPage() {
  const [message, setMessage] = useState("Securing the Prava connection…");

  useEffect(() => {
    const search = new URLSearchParams(window.location.search);
    const state = search.get("state");
    const code = search.get("code");
    if (!state || !code) {
      queueMicrotask(() => setMessage("Prava did not return a complete authorization response."));
      return;
    }
    void fetch("/v1/connectors/prava/callback", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...buyerDevelopmentHeaders },
      body: JSON.stringify({ state, code }),
    })
      .then((response) => {
        if (!response.ok) throw new Error("Prava connection failed");
        window.location.replace("/sira?panel=connectors&prava=connected");
      })
      .catch(() => {
        setMessage("Prava could not be connected. Return to SIRA and try again.");
      });
  }, []);

  return (
    <main style={{ display: "grid", minHeight: "100vh", placeItems: "center", padding: "2rem" }}>
      <p role="status">{message}</p>
    </main>
  );
}
