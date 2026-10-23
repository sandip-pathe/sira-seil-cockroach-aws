"use client";

/**
 * A deliberately small, content-free browser instrumentation boundary.
 * Events are exposed to an in-page observer only; this module does not persist
 * or transmit them. Canonical server events remain the source of truth for
 * confirmed business state. External outcomes require an authoritative source.
 */
export type InstrumentationEvent =
  | {
      schema_version: 1;
      layer: "ui_intent";
      name: "exchange.evidence.publish" | "exchange.offer.propose" | "exchange.offer.accept" | "exchange.offer.approve" | "exchange.handoff.prepare" | "exchange.handoff.open";
      surface: "exchange";
      occurred_at: string;
    }
  | {
      schema_version: 1;
      layer: "server_effect";
      name: "exchange.evidence.publish" | "exchange.offer.propose" | "exchange.offer.accept" | "exchange.offer.approve" | "exchange.handoff.prepare" | "exchange.handoff.open";
      surface: "exchange";
      confirmation: "api_ack";
      occurred_at: string;
    }
  | {
      schema_version: 1;
      layer: "external_outcome";
      name: "procurement.completed" | "procurement.failed";
      surface: "exchange";
      source: "provider_webhook" | "human_attestation";
      certainty: "confirmed" | "reported" | "inconclusive";
      occurred_at: string;
    }
  | {
      schema_version: 1;
      layer: "performance";
      metric: "TTFB" | "DOM_CONTENT_LOADED" | "LOAD" | "LCP" | "CLS" | "EVENT_DURATION_MAX";
      value: number;
      unit: "ms" | "score";
      occurred_at: string;
    };

type ProductAction = Extract<InstrumentationEvent, { layer: "ui_intent" | "server_effect" }>;

function publish(event: InstrumentationEvent): void {
  if (typeof window === "undefined") return;
  // Rebuild from allowlisted fields; never forward a caller-supplied object.
  let safe: InstrumentationEvent;
  if (event.layer === "ui_intent") {
    safe = { schema_version: 1, layer: event.layer, name: event.name, surface: event.surface, occurred_at: event.occurred_at };
  } else if (event.layer === "server_effect") {
    safe = { schema_version: 1, layer: event.layer, name: event.name, surface: event.surface, confirmation: event.confirmation, occurred_at: event.occurred_at };
  } else if (event.layer === "external_outcome") {
    safe = { schema_version: 1, layer: event.layer, name: event.name, surface: event.surface, source: event.source, certainty: event.certainty, occurred_at: event.occurred_at };
  } else {
    safe = { schema_version: 1, layer: event.layer, metric: event.metric, value: event.value, unit: event.unit, occurred_at: event.occurred_at };
  }
  window.dispatchEvent(new CustomEvent("sira:instrumentation", { detail: safe }));
}

export function recordUiIntent(name: ProductAction["name"]): void {
  publish({ schema_version: 1, layer: "ui_intent", name, surface: "exchange", occurred_at: new Date().toISOString() });
}

/** Call only after an authoritative API mutation has acknowledged the effect. */
export function recordServerEffect(name: ProductAction["name"]): void {
  publish({ schema_version: 1, layer: "server_effect", name, surface: "exchange", confirmation: "api_ack", occurred_at: new Date().toISOString() });
}

export function recordPerformance(metric: Extract<InstrumentationEvent, { layer: "performance" }>['metric'], value: number, unit: "ms" | "score"): void {
  if (!Number.isFinite(value) || value < 0) return;
  publish({ schema_version: 1, layer: "performance", metric, value: Math.round(value * 100) / 100, unit, occurred_at: new Date().toISOString() });
}
