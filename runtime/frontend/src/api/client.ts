import type { DebateConfig, RunMetadata } from "@/types";

const BASE = "/api";

/** Thrown when the API returns a non-2xx response. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE}${path}`);
  if (!response.ok) {
    throw new ApiError(`GET ${path} failed`, response.status);
  }
  return response.json() as Promise<T>;
}

export const api = {
  listRuns: () => get<RunMetadata[]>("/debate/runs"),

  getRun: (runId: string) => get<unknown>(`/debate/runs/${runId}`),

  /** Direct download links — the browser handles the save dialog. */
  exportMarkdownUrl: (runId: string) => `${BASE}/debate/runs/${runId}/export.md`,
  exportHtmlUrl: (runId: string) => `${BASE}/debate/runs/${runId}/export.html`,

  /** Opens the SSE stream for a new debate. See useDebateStream. */
  streamUrl: () => `${BASE}/debate/stream`,

  streamBody: (config: DebateConfig) => JSON.stringify(config),
};
