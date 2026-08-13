import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const inputPath = path.join(root, "contracts", "openapi", "openapi.json");
const outputDir = path.join(root, "packages", "api-client", "src");
const check = process.argv.includes("--check");
const openapi = JSON.parse(fs.readFileSync(inputPath, "utf8"));

function refName(reference) {
  return reference.split("/").at(-1);
}

function propertyName(value) {
  return /^[A-Za-z_$][A-Za-z0-9_$]*$/.test(value) ? value : JSON.stringify(value);
}

function typeFor(schema) {
  if (!schema) return "unknown";
  if (schema.$ref) return refName(schema.$ref);
  if (Object.hasOwn(schema, "const")) return JSON.stringify(schema.const);
  if (schema.enum) return schema.enum.map((value) => JSON.stringify(value)).join(" | ");
  if (schema.anyOf) return schema.anyOf.map(typeFor).join(" | ");
  if (schema.oneOf) return schema.oneOf.map(typeFor).join(" | ");
  if (schema.allOf) return schema.allOf.map(typeFor).join(" & ");
  if (schema.type === "array") {
    const itemType = typeFor(schema.items);
    return itemType.includes(" | ") ? `Array<${itemType}>` : `${itemType}[]`;
  }
  if (schema.type === "object" || schema.properties) {
    const properties = schema.properties ?? {};
    const required = new Set(schema.required ?? []);
    const fields = Object.entries(properties).map(
      ([name, value]) =>
        `${propertyName(name)}${required.has(name) ? "" : "?"}: ${typeFor(value)};`,
    );
    if (schema.additionalProperties === true) fields.push("[key: string]: unknown;");
    if (schema.additionalProperties && typeof schema.additionalProperties === "object") {
      fields.push(`[key: string]: ${typeFor(schema.additionalProperties)};`);
    }
    return `{ ${fields.join(" ")} }`;
  }
  if (schema.type === "integer" || schema.type === "number") return "number";
  if (schema.type === "boolean") return "boolean";
  if (schema.type === "null") return "null";
  if (schema.type === "string") return "string";
  return "unknown";
}

function renderComponent(name, schema) {
  if ((schema.type === "object" || schema.properties) && !schema.anyOf && !schema.allOf) {
    const required = new Set(schema.required ?? []);
    const fields = Object.entries(schema.properties ?? {}).map(
      ([property, value]) =>
        `  ${propertyName(property)}${required.has(property) ? "" : "?"}: ${typeFor(value)};`,
    );
    if (schema.additionalProperties === true) fields.push("  [key: string]: unknown;");
    if (schema.additionalProperties && typeof schema.additionalProperties === "object") {
      fields.push(`  [key: string]: ${typeFor(schema.additionalProperties)};`);
    }
    return `export interface ${name} {\n${fields.join("\n")}\n}`;
  }
  return `export type ${name} = ${typeFor(schema)};`;
}

function successResponse(operation) {
  const success = Object.entries(operation.responses ?? {})
    .filter(([status]) => /^2\d\d$/.test(status))
    .sort(([left], [right]) => left.localeCompare(right))[0]?.[1];
  const representations = Object.entries(success?.content ?? {});
  if (representations.length === 0) return { mediaType: null, schema: null };
  const preferred =
    representations.find(([mediaType]) => mediaType === "application/json") ??
    representations.find(([mediaType]) => mediaType.endsWith("+json")) ??
    representations.find(([mediaType]) => mediaType === "text/event-stream") ??
    representations[0];
  return { mediaType: preferred[0], schema: preferred[1]?.schema ?? null };
}

function responseTypeFor({ mediaType, schema }) {
  if (!mediaType) return "undefined";
  if (mediaType === "application/json" || mediaType.endsWith("+json")) {
    return typeFor(schema);
  }
  if (mediaType === "text/event-stream") return "ReadableStream<Uint8Array>";
  if (mediaType.startsWith("text/")) return "string";
  return "ArrayBuffer";
}

const operations = [];
for (const [routePath, pathItem] of Object.entries(openapi.paths)) {
  for (const method of ["get", "post", "put", "patch", "delete"]) {
    const operation = pathItem[method];
    if (!operation) continue;
    const parameters = [...(pathItem.parameters ?? []), ...(operation.parameters ?? [])];
    const pathParameters = parameters.filter((parameter) => parameter.in === "path");
    const queryParameters = parameters.filter((parameter) => parameter.in === "query");
    const pathType = pathParameters.length
      ? `{ ${pathParameters
          .map(
            (parameter) =>
              `${propertyName(parameter.name)}${parameter.required ? "" : "?"}: ${typeFor(parameter.schema)};`,
          )
          .join(" ")} }`
      : "Record<never, never>";
    const queryType = queryParameters.length
      ? `{ ${queryParameters
          .map(
            (parameter) =>
              `${propertyName(parameter.name)}${parameter.required ? "" : "?"}: ${typeFor(parameter.schema)};`,
          )
          .join(" ")} }`
      : "Record<never, never>";
    const bodyContent = operation.requestBody?.content ?? {};
    const bodyMediaType = Object.hasOwn(bodyContent, "application/json")
      ? "application/json"
      : Object.hasOwn(bodyContent, "multipart/form-data")
        ? "multipart/form-data"
        : null;
    const bodySchema = bodyMediaType ? bodyContent[bodyMediaType]?.schema : undefined;
    const response = successResponse(operation);
    operations.push({
      id: operation.operationId,
      method: method.toUpperCase(),
      path: routePath,
      pathType,
      queryType,
      bodyType:
        bodyMediaType === "multipart/form-data"
          ? "FormData"
          : bodySchema
            ? typeFor(bodySchema)
            : "never",
      bodyMediaType,
      responseType: responseTypeFor(response),
      responseMediaType: response.mediaType,
      idempotency: parameters.some(
        (parameter) => parameter.in === "header" && parameter.name === "Idempotency-Key",
      ),
    });
  }
}
operations.sort((left, right) => left.id.localeCompare(right.id));

const typesSource = `// Generated from contracts/openapi/openapi.json. Do not edit by hand.\n\n${Object.entries(
  openapi.components.schemas,
)
  .sort(([left], [right]) => left.localeCompare(right))
  .map(([name, schema]) => renderComponent(name, schema))
  .join("\n\n")}\n\nexport interface Operations {\n${operations
  .map(
    (operation) =>
      `  ${propertyName(operation.id)}: { method: ${JSON.stringify(operation.method)}; path: ${JSON.stringify(operation.path)}; pathParams: ${operation.pathType}; queryParams: ${operation.queryType}; body: ${operation.bodyType}; response: ${operation.responseType}; requiresIdempotency: ${operation.idempotency}; };`,
  )
  .join("\n")}\n}\n\nexport type OperationId = keyof Operations;\n`;

const operationRuntime = operations
  .map(
    (operation) =>
      `  ${propertyName(operation.id)}: { method: ${JSON.stringify(operation.method)}, path: ${JSON.stringify(operation.path)}, bodyMediaType: ${JSON.stringify(operation.bodyMediaType)}, responseMediaType: ${JSON.stringify(operation.responseMediaType)} },`,
  )
  .join("\n");

const clientSource = `// Generated from contracts/openapi/openapi.json. Do not edit by hand.\n\nimport type { OperationId, Operations } from "./types";\n\nconst operations = {\n${operationRuntime}\n} as const;\n\ntype PathInput<K extends OperationId> = keyof Operations[K]["pathParams"] extends never\n  ? { pathParams?: never }\n  : { pathParams: Operations[K]["pathParams"] };\n\ntype BodyInput<K extends OperationId> = Operations[K]["body"] extends never\n  ? { body?: never }\n  : { body: Operations[K]["body"] };\n\ntype IdempotencyInput<K extends OperationId> = Operations[K]["requiresIdempotency"] extends true\n  ? { idempotencyKey: string }\n  : { idempotencyKey?: string };\n\nexport type RequestInput<K extends OperationId> = PathInput<K> &\n  BodyInput<K> &\n  IdempotencyInput<K> & { headers?: Record<string, string>; signal?: AbortSignal };\n\nexport class ApiClientError extends Error {\n  constructor(\n    public readonly status: number,\n    public readonly payload: unknown,\n  ) {\n    super(\`SIRA API request failed with HTTP \${status}\`);\n    this.name = "ApiClientError";\n  }\n}\n\nexport class ApiClientResponseTypeError extends Error {\n  constructor(\n    message: string,\n    public readonly mediaType: string | null,\n  ) {\n    super(message);\n    this.name = "ApiClientResponseTypeError";\n  }\n}\n\nfunction normalizedMediaType(value: string | null): string | null {\n  return value?.split(";", 1)[0]?.trim().toLowerCase() || null;\n}\n\nfunction isJsonMediaType(value: string | null): boolean {\n  return value === "application/json" || value?.endsWith("+json") === true;\n}\n\nasync function readErrorPayload(response: Response): Promise<unknown> {\n  const text = await response.text();\n  if (!text) return undefined;\n  if (!isJsonMediaType(normalizedMediaType(response.headers.get("Content-Type")))) return text;\n  try {\n    return JSON.parse(text) as unknown;\n  } catch {\n    return text;\n  }\n}\n\nexport class SiraApiClient {\n  constructor(\n    private readonly baseUrl: string,\n    private readonly fetcher: typeof fetch = fetch,\n  ) {}\n\n  private async performRequest<K extends OperationId>(\n    operationId: K,\n    input: RequestInput<K>,\n    accept?: string,\n  ): Promise<Response> {\n    const operation = operations[operationId];\n    let route: string = operation.path;\n    const pathParams = (input as { pathParams?: Record<string, string | number> }).pathParams ?? {};\n    for (const [name, value] of Object.entries(pathParams)) {\n      route = route.replace(\`{\${name}}\`, encodeURIComponent(String(value)));\n    }\n    if (/\\{[^}]+\\}/.test(route)) throw new Error("Missing generated-client path parameter");\n\n    const headers = new Headers(input.headers);\n    const body = (input as { body?: unknown }).body;\n    const idempotencyKey = (input as { idempotencyKey?: string }).idempotencyKey;\n    if (accept && !headers.has("Accept")) headers.set("Accept", accept);\n    if (idempotencyKey) headers.set("Idempotency-Key", idempotencyKey);\n    if (body !== undefined) headers.set("Content-Type", "application/json");\n\n    const response = await this.fetcher(new URL(route, this.baseUrl), {\n      method: operation.method,\n      headers,\n      body: body === undefined ? undefined : JSON.stringify(body),\n      signal: input.signal,\n    });\n    if (!response.ok) throw new ApiClientError(response.status, await readErrorPayload(response));\n    return response;\n  }\n\n  async requestRaw<K extends OperationId>(\n    operationId: K,\n    input: RequestInput<K>,\n  ): Promise<Response> {\n    return this.performRequest(operationId, input);\n  }\n\n  async requestStream<K extends OperationId>(\n    operationId: K,\n    input: RequestInput<K>,\n  ): Promise<ReadableStream<Uint8Array>> {\n    const response = await this.performRequest(operationId, input, "text/event-stream");\n    const mediaType = normalizedMediaType(response.headers.get("Content-Type"));\n    if (mediaType !== "text/event-stream") {\n      response.body?.cancel().catch(() => undefined);\n      throw new ApiClientResponseTypeError(\n        \`Expected text/event-stream but received \${mediaType ?? "an unspecified media type"}\`,\n        mediaType,\n      );\n    }\n    if (!response.body) {\n      throw new ApiClientResponseTypeError("The event stream response had no body", mediaType);\n    }\n    return response.body;\n  }\n\n  async request<K extends OperationId>(\n    operationId: K,\n    input: RequestInput<K>,\n  ): Promise<Operations[K]["response"]> {\n    const operation = operations[operationId];\n    const response = await this.performRequest(operationId, input);\n    const mediaType =\n      normalizedMediaType(response.headers.get("Content-Type")) ?? operation.responseMediaType;\n\n    if (response.status === 204 || response.status === 205) {\n      return undefined as unknown as Operations[K]["response"];\n    }\n    if (mediaType === "text/event-stream") {\n      if (!response.body) {\n        throw new ApiClientResponseTypeError("The event stream response had no body", mediaType);\n      }\n      return response.body as Operations[K]["response"];\n    }\n    if (isJsonMediaType(mediaType)) {\n      const text = await response.text();\n      if (!text) return undefined as unknown as Operations[K]["response"];\n      try {\n        return JSON.parse(text) as Operations[K]["response"];\n      } catch {\n        throw new ApiClientResponseTypeError("The response body was not valid JSON", mediaType);\n      }\n    }\n    if (mediaType?.startsWith("text/") === true) {\n      return (await response.text()) as unknown as Operations[K]["response"];\n    }\n    return (await response.arrayBuffer()) as unknown as Operations[K]["response"];\n  }\n}\n`;

const queryAwareClientSource = clientSource
  .replace(
    "type BodyInput<K extends OperationId>",
    `type QueryInput<K extends OperationId> = keyof Operations[K]["queryParams"] extends never
  ? { query?: never }
  : { query?: Operations[K]["queryParams"] };

type BodyInput<K extends OperationId>`,
  )
  .replace(
    "export type RequestInput<K extends OperationId> = PathInput<K> &\n  BodyInput<K>",
    "export type RequestInput<K extends OperationId> = PathInput<K> &\n  QueryInput<K> &\n  BodyInput<K>",
  )
  .replace(
    '    if (/\\{[^}]+\\}/.test(route)) throw new Error("Missing generated-client path parameter");\n\n    const headers',
    `    if (/\\{[^}]+\\}/.test(route)) throw new Error("Missing generated-client path parameter");

    const url = new URL(route, this.baseUrl);
    const query = (input as { query?: Record<string, unknown> }).query ?? {};
    for (const [name, value] of Object.entries(query)) {
      if (value === undefined || value === null) continue;
      if (Array.isArray(value)) {
        for (const item of value) url.searchParams.append(name, String(item));
      } else {
        url.searchParams.set(name, String(value));
      }
    }

    const headers`,
  )
  .replace("this.fetcher(new URL(route, this.baseUrl),", "this.fetcher.call(globalThis, url,");

const mediaAwareClientSource = queryAwareClientSource
  .replace(
    '    if (body !== undefined) headers.set("Content-Type", "application/json");\n\n    const response',
    `    if (body !== undefined && operation.bodyMediaType === "application/json") {
      headers.set("Content-Type", "application/json");
    }
    const requestBody = operation.bodyMediaType === "multipart/form-data"
      ? body as FormData
      : body === undefined
        ? undefined
        : JSON.stringify(body);

    const response`,
  )
  .replace("body: body === undefined ? undefined : JSON.stringify(body),", "body: requestBody,");

const indexSource = `// Generated from contracts/openapi/openapi.json. Do not edit by hand.\nexport * from "./client";\nexport * from "./types";\nexport const contractVersion = ${JSON.stringify(openapi.info.version)} as const;\n`;

const outputs = new Map([
  [path.join(outputDir, "types.ts"), typesSource],
  [path.join(outputDir, "client.ts"), mediaAwareClientSource],
  [path.join(outputDir, "index.ts"), indexSource],
]);

let drift = false;
for (const [filePath, source] of outputs) {
  if (check) {
    if (!fs.existsSync(filePath) || fs.readFileSync(filePath, "utf8") !== source) {
      console.error(`Generated client drift: ${path.relative(root, filePath)}`);
      drift = true;
    }
  } else {
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, source, "utf8");
    console.log(`Wrote ${path.relative(root, filePath)}`);
  }
}
if (drift) process.exit(1);
