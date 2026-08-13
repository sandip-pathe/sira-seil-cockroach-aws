import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Payment handoff",
  description: "A provider-neutral, human-controlled payment handoff from SIRA.",
};

export default function PaymentHandoffPage() {
  return (
    <main
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        padding: "2rem",
        background: "#f4f1e9",
        color: "#18211b",
      }}
    >
      <section
        style={{
          width: "min(42rem, 100%)",
          padding: "2rem",
          border: "1px solid #c8c4b8",
          borderRadius: "1rem",
          background: "#fffdf7",
          boxShadow: "0 1rem 3rem rgba(26, 40, 31, 0.08)",
        }}
      >
        <p
          style={{
            margin: "0 0 .75rem",
            fontWeight: 700,
            letterSpacing: ".08em",
            textTransform: "uppercase",
            color: "#496858",
          }}
        >
          SIRA payment handoff
        </p>
        <h1 style={{ margin: "0 0 1rem", fontSize: "clamp(2rem, 6vw, 3.5rem)", lineHeight: 1 }}>
          The buyer stays in control.
        </h1>
        <p style={{ fontSize: "1.1rem", lineHeight: 1.6 }}>
          This is the provider-neutral payment boundary. In production, configure{" "}
          <code>NEXT_PUBLIC_PAYMENT_WORKSPACE_URL</code> to open the organization&apos;s approved
          payment provider after the exact offer is approved.
        </p>
        <div
          style={{
            margin: "1.5rem 0",
            padding: "1rem",
            borderRadius: ".75rem",
            background: "#edf3ee",
          }}
        >
          <strong>No charge was initiated.</strong>
          <p style={{ margin: ".4rem 0 0", lineHeight: 1.5 }}>
            SIRA does not send card credentials, mark payment complete from a browser redirect, or
            let an agent spend without human approval.
          </p>
        </div>
        <Link href="/payment/open" target="_blank" rel="noreferrer">
          Open payment workspace
        </Link>{" "}
        <Link
          href="/sira"
          style={{
            display: "inline-block",
            padding: ".8rem 1rem",
            borderRadius: ".65rem",
            background: "#193a2a",
            color: "white",
            textDecoration: "none",
            fontWeight: 700,
          }}
        >
          Return to SIRA
        </Link>
      </section>
    </main>
  );
}
