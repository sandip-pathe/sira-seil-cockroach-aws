# Instrumentation boundaries

The web app exposes a versioned, content-free event envelope through the in-page `sira:instrumentation` browser event. It does not persist events or send them to an analytics service. The envelope has separate layers for `ui_intent`, an `api_ack`-confirmed `server_effect`, and an `external_outcome` attributed to a provider webhook or human attestation. It contains no user, tenant, case, product, prompt, message, offer, price, or URL identifiers.

The governed exchange records intent at mutation start and records a server effect only after a successful API response. Errors do not become effects. Preparing or opening a payment handoff is not evidence that procurement completed; no external outcome is emitted by the current browser flow. Canonical server event journals remain the source of truth for business state.

`PerformanceBaseline` exposes navigation TTFB, DOM content loaded, load, largest contentful paint, cumulative layout shift, and maximum observed event duration. These are an initial browser baseline, not a production dashboard or a complete Core Web Vitals implementation. In particular, `EVENT_DURATION_MAX` is not labeled INP. Metrics contain only a numeric value, fixed metric name, unit, and timestamp. An in-page consumer can listen to the event without receiving the current URL or page content.

No session replay, raw prompt capture, private-content analytics, external telemetry vendor, persistence, or attribution-based conversion claim is enabled. Any future exporter must preserve the allowlist, tenant privacy boundary, retention limits, and source/certainty distinction.
