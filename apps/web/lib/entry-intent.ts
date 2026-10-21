"use client";

export type EntryWorkspace = "sira" | "seil";

const STORAGE_KEY = "sira.entry-intent.v1";
const MAX_AGE_MS = 30 * 60 * 1000;

function hasPathPrefix(pathname: string, prefix: string): boolean {
  return pathname === prefix || pathname.startsWith(`${prefix}/`);
}

/** Accept only same-origin, supported workspace routes; reject auth loops and open redirects. */
export function sanitizeEntryTarget(target: string, workspace: EntryWorkspace): string | null {
  if (!target.startsWith("/") || target.startsWith("//") || target.includes("\\") || target.length > 4096) return null;
  let url: URL;
  try {
    url = new URL(target, "https://sira.invalid");
  } catch {
    return null;
  }
  if (url.origin !== "https://sira.invalid") return null;
  if (["/sign-in", "/sira/sign-in", "/seil/sign-in"].some((path) => hasPathPrefix(url.pathname, path))) return null;

  if (hasPathPrefix(url.pathname, "/exchange")) {
    const mode = url.searchParams.get("mode");
    if (workspace === "seil") return mode === "seil" ? `${url.pathname}${url.search}${url.hash}` : null;
    return mode !== "seil" ? `${url.pathname}${url.search}${url.hash}` : null;
  }

  const allowed = workspace === "seil" ? ["/seil", "/seller"] : ["/sira", "/decisions", "/matches", "/integrity"];
  return allowed.some((prefix) => hasPathPrefix(url.pathname, prefix))
    ? `${url.pathname}${url.search}${url.hash}`
    : null;
}

export function workspaceForEntry(pathname: string, search: string): EntryWorkspace {
  if (hasPathPrefix(pathname, "/seil") || hasPathPrefix(pathname, "/seller")) return "seil";
  if (hasPathPrefix(pathname, "/exchange") && new URLSearchParams(search).get("mode") === "seil") return "seil";
  return "sira";
}

export function rememberEntryIntent(workspace: EntryWorkspace, target: string): void {
  const safeTarget = sanitizeEntryTarget(target, workspace);
  if (!safeTarget) return;
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ workspace, target: safeTarget, savedAt: Date.now() }));
  } catch {
    // Storage can be disabled; sign-in still has the correct workspace fallback.
  }
}

function readStoredEntryIntent(workspace: EntryWorkspace): string | null {
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object") return null;
    const candidate = value as { workspace?: unknown; target?: unknown; savedAt?: unknown };
    if (candidate.workspace !== workspace || typeof candidate.target !== "string" || typeof candidate.savedAt !== "number") return null;
    if (Date.now() - candidate.savedAt < 0 || Date.now() - candidate.savedAt > MAX_AGE_MS) return null;
    return sanitizeEntryTarget(candidate.target, workspace);
  } catch {
    return null;
  }
}

export function hasEntryIntent(workspace: EntryWorkspace, explicitTarget?: string): boolean {
  return Boolean((explicitTarget && sanitizeEntryTarget(explicitTarget, workspace)) || readStoredEntryIntent(workspace));
}

export function consumeEntryIntent(workspace: EntryWorkspace, explicitTarget?: string): string | null {
  let stored: string | null = null;
  try {
    stored = readStoredEntryIntent(workspace);
    window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Continue with an explicit target if storage is disabled.
  }
  return (explicitTarget && sanitizeEntryTarget(explicitTarget, workspace)) || stored;
}
