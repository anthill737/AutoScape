export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function defaultApiErrorMessage(res: Response): string {
  const status = res.status ? ` (HTTP ${res.status})` : "";
  return `Request failed${status}`;
}

export async function parseApiError(
  res: Response,
  fallback = defaultApiErrorMessage(res),
): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === "string" && body.detail.trim()) {
      return body.detail;
    }
  } catch {
    // Fall back when the response is not JSON or has an empty body.
  }
  return fallback;
}
