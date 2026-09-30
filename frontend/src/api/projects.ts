import type { DesignRequestOut } from "./designRequests";
import { parseApiError } from "./errors";

export interface ProjectListItem {
  id: number;
  address: string;
  /** "exterior" | "interior"; absent on rows from older backends (treat as exterior). */
  space_type?: string;
  room_type?: string | null;
  space_details?: Record<string, number> | null;
  space_label?: string;
  site_photo_url: string | null;
  site_photo_thumb_url?: string | null;
  created_at: string;
  latest_design_request_at?: string | null;
  design_request_count: number;
  render_count: number;
  iteration_count: number;
  has_chosen_render: boolean;
  has_build_sheet: boolean;
  latest_quality_tier?: string | null;
}

export interface ProjectDetail {
  id: number;
  address: string;
  space_type?: string;
  room_type?: string | null;
  space_details?: Record<string, number> | null;
  space_label?: string;
  lot_size_sqft: number | null;
  house_sqft: number | null;
  site_photo_url: string | null;
  created_at: string;
  design_requests: DesignRequestOut[];
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * fetch() with automatic retry for transient failures.
 *
 * The backend can take several seconds to finish starting (DB migrations,
 * CodeGraph, Playwright MCP, etc.) while the dev server is already serving the
 * page. A request fired during that window fails with a connection error or a
 * 5xx, and previously that error was shown to the user permanently until they
 * manually hard-refreshed. Instead we retry a handful of times with a short
 * delay, so the very first load succeeds on its own once the backend is ready.
 *
 * Only safe-to-repeat conditions are retried:
 *   - network/connection errors (backend not accepting connections yet)
 *   - HTTP 5xx (backend up but not fully ready, or transient proxy error)
 * 4xx responses are NOT retried — they are real client errors that won't fix
 * themselves. This helper is only used for idempotent GETs; POST/create calls
 * deliberately do not use it to avoid duplicate writes.
 */
/** Retry tuning for fetchWithRetry. Exported so tests can shorten the delay. */
export const fetchRetryOptions = { retries: 8, delayMs: 750 };

async function fetchWithRetry(
  input: RequestInfo,
  init?: RequestInit,
  retries = fetchRetryOptions.retries,
  delayMs = fetchRetryOptions.delayMs,
): Promise<Response> {
  let lastErr: unknown;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(input, init);
      if (res.status >= 500 && attempt < retries) {
        await sleep(delayMs);
        continue;
      }
      return res;
    } catch (err) {
      lastErr = err;
      if (attempt < retries) {
        await sleep(delayMs);
        continue;
      }
      throw lastErr;
    }
  }
  throw lastErr ?? new Error("Request failed");
}

export async function listProjects(): Promise<ProjectListItem[]> {
  const res = await fetchWithRetry("/api/projects");
  if (!res.ok) {
    throw new Error(await parseApiError(res, `Failed to fetch projects: ${res.status}`));
  }
  return res.json();
}

export async function getProject(id: number): Promise<ProjectDetail> {
  const res = await fetchWithRetry(`/api/projects/${id}`);
  if (!res.ok) {
    throw new Error(await parseApiError(res, `Failed to fetch project: ${res.status}`));
  }
  return res.json();
}

export async function createProject(
  data: FormData,
): Promise<{ id: number; address: string; created_at: string }> {
  // Not retried: a POST that partially succeeded could create a duplicate.
  const res = await fetch("/api/projects", { method: "POST", body: data });
  if (!res.ok) {
    throw new Error(await parseApiError(res));
  }
  return res.json();
}
