// Generated from contracts/openapi/openapi.json. Do not edit by hand.

import type { OperationId, Operations } from "./types";

const operations = {
  accept_proposal: { method: "POST", path: "/v1/purchase-briefs/{brief_id}/proposals/{proposal_id}/accept", responseMediaType: "application/json" },
  approve: { method: "POST", path: "/v1/approval-requests/{approval_id}/approve", responseMediaType: "application/json" },
  candidate_action: { method: "POST", path: "/v1/purchase-requests/{request_id}/candidates/{candidate_id}/actions", responseMediaType: "application/json" },
  create_approval_request: { method: "POST", path: "/v1/purchase-intents/{intent_id}/approval-requests", responseMediaType: "application/json" },
  create_prava_session: { method: "POST", path: "/v1/purchase-intents/{intent_id}/prava-sessions", responseMediaType: "application/json" },
  create_purchase_request: { method: "POST", path: "/v1/purchase-requests", responseMediaType: "application/json" },
  discover: { method: "POST", path: "/v1/purchase-requests/{request_id}/discover", responseMediaType: "application/json" },
  get_counterfactuals: { method: "GET", path: "/v1/decisions/{decision_id}/counterfactuals", responseMediaType: "application/json" },
  get_decision: { method: "GET", path: "/v1/decisions/{decision_id}", responseMediaType: "application/json" },
  get_decision_view: { method: "GET", path: "/v1/purchase-requests/{request_id}/decision-view", responseMediaType: "application/json" },
  get_purchase_brief: { method: "GET", path: "/v1/purchase-requests/{request_id}/purchase-brief", responseMediaType: "application/json" },
  get_purchase_request: { method: "GET", path: "/v1/purchase-requests/{request_id}", responseMediaType: "application/json" },
  get_receipt: { method: "GET", path: "/v1/purchases/{purchase_id}/receipt", responseMediaType: "application/json" },
  get_requirement_brief: { method: "GET", path: "/v1/requirement-briefs/{brief_id}", responseMediaType: "application/json" },
  get_stackfile: { method: "GET", path: "/v1/organizations/{organization_id}/stackfile", responseMediaType: "application/json" },
  get_workflow: { method: "GET", path: "/v1/workflows/{workflow_id}", responseMediaType: "application/json" },
  get_workflow_events: { method: "GET", path: "/v1/workflows/{workflow_id}/events", responseMediaType: "text/event-stream" },
  health: { method: "GET", path: "/health", responseMediaType: "application/json" },
  lock_purchase_intent: { method: "POST", path: "/v1/decisions/{decision_id}/purchase-intents", responseMediaType: "application/json" },
  purchase_status: { method: "GET", path: "/v1/purchase-intents/{intent_id}/status", responseMediaType: "application/json" },
  record_consent: { method: "POST", path: "/v1/engagements/{engagement_id}/consent", responseMediaType: "application/json" },
  reject_proposal: { method: "POST", path: "/v1/purchase-briefs/{brief_id}/proposals/{proposal_id}/reject", responseMediaType: "application/json" },
  replay_evaluation: { method: "POST", path: "/v1/evaluation-runs/{evaluation_run_id}/replay", responseMediaType: "application/json" },
  reset_demo: { method: "POST", path: "/v1/demo/reset", responseMediaType: "application/json" },
  run_calibration: { method: "POST", path: "/v1/purchase-requests/{request_id}/calibration-runs", responseMediaType: "application/json" },
  simulate_decision: { method: "POST", path: "/v1/decisions/{decision_id}/simulations", responseMediaType: "application/json" },
} as const;

type PathInput<K extends OperationId> = keyof Operations[K]["pathParams"] extends never
  ? { pathParams?: never }
  : { pathParams: Operations[K]["pathParams"] };

type BodyInput<K extends OperationId> = Operations[K]["body"] extends never
  ? { body?: never }
  : { body: Operations[K]["body"] };

type IdempotencyInput<K extends OperationId> = Operations[K]["requiresIdempotency"] extends true
  ? { idempotencyKey: string }
  : { idempotencyKey?: string };

export type RequestInput<K extends OperationId> = PathInput<K> &
  BodyInput<K> &
  IdempotencyInput<K> & { headers?: Record<string, string>; signal?: AbortSignal };

export class ApiClientError extends Error {
  constructor(
    public readonly status: number,
    public readonly payload: unknown,
  ) {
    super(`SIRA API request failed with HTTP ${status}`);
    this.name = "ApiClientError";
  }
}

export class ApiClientResponseTypeError extends Error {
  constructor(
    message: string,
    public readonly mediaType: string | null,
  ) {
    super(message);
    this.name = "ApiClientResponseTypeError";
  }
}

function normalizedMediaType(value: string | null): string | null {
  return value?.split(";", 1)[0]?.trim().toLowerCase() || null;
}

function isJsonMediaType(value: string | null): boolean {
  return value === "application/json" || value?.endsWith("+json") === true;
}

async function readErrorPayload(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return undefined;
  if (!isJsonMediaType(normalizedMediaType(response.headers.get("Content-Type")))) return text;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

export class SiraApiClient {
  constructor(
    private readonly baseUrl: string,
    private readonly fetcher: typeof fetch = fetch,
  ) {}

  private async performRequest<K extends OperationId>(
    operationId: K,
    input: RequestInput<K>,
    accept?: string,
  ): Promise<Response> {
    const operation = operations[operationId];
    let route: string = operation.path;
    const pathParams = (input as { pathParams?: Record<string, string | number> }).pathParams ?? {};
    for (const [name, value] of Object.entries(pathParams)) {
      route = route.replace(`{${name}}`, encodeURIComponent(String(value)));
    }
    if (/\{[^}]+\}/.test(route)) throw new Error("Missing generated-client path parameter");

    const headers = new Headers(input.headers);
    const body = (input as { body?: unknown }).body;
    const idempotencyKey = (input as { idempotencyKey?: string }).idempotencyKey;
    if (accept && !headers.has("Accept")) headers.set("Accept", accept);
    if (idempotencyKey) headers.set("Idempotency-Key", idempotencyKey);
    if (body !== undefined) headers.set("Content-Type", "application/json");

    const response = await this.fetcher(new URL(route, this.baseUrl), {
      method: operation.method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: input.signal,
    });
    if (!response.ok) throw new ApiClientError(response.status, await readErrorPayload(response));
    return response;
  }

  async requestRaw<K extends OperationId>(
    operationId: K,
    input: RequestInput<K>,
  ): Promise<Response> {
    return this.performRequest(operationId, input);
  }

  async requestStream<K extends OperationId>(
    operationId: K,
    input: RequestInput<K>,
  ): Promise<ReadableStream<Uint8Array>> {
    const response = await this.performRequest(operationId, input, "text/event-stream");
    const mediaType = normalizedMediaType(response.headers.get("Content-Type"));
    if (mediaType !== "text/event-stream") {
      response.body?.cancel().catch(() => undefined);
      throw new ApiClientResponseTypeError(
        `Expected text/event-stream but received ${mediaType ?? "an unspecified media type"}`,
        mediaType,
      );
    }
    if (!response.body) {
      throw new ApiClientResponseTypeError("The event stream response had no body", mediaType);
    }
    return response.body;
  }

  async request<K extends OperationId>(
    operationId: K,
    input: RequestInput<K>,
  ): Promise<Operations[K]["response"]> {
    const operation = operations[operationId];
    const response = await this.performRequest(operationId, input);
    const mediaType =
      normalizedMediaType(response.headers.get("Content-Type")) ?? operation.responseMediaType;

    if (response.status === 204 || response.status === 205) {
      return undefined as unknown as Operations[K]["response"];
    }
    if (mediaType === "text/event-stream") {
      if (!response.body) {
        throw new ApiClientResponseTypeError("The event stream response had no body", mediaType);
      }
      return response.body as Operations[K]["response"];
    }
    if (isJsonMediaType(mediaType)) {
      const text = await response.text();
      if (!text) return undefined as unknown as Operations[K]["response"];
      try {
        return JSON.parse(text) as Operations[K]["response"];
      } catch {
        throw new ApiClientResponseTypeError("The response body was not valid JSON", mediaType);
      }
    }
    if (mediaType?.startsWith("text/") === true) {
      return (await response.text()) as unknown as Operations[K]["response"];
    }
    return (await response.arrayBuffer()) as unknown as Operations[K]["response"];
  }
}
