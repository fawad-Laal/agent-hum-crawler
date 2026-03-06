/**
 * Project Phoenix — API Client
 * Type-safe wrapper around the Moltis dashboard API (port 8788).
 * Zod schemas validate all responses at runtime.
 *
 * Phase B complete: long-running POST endpoints return 202 + job_id.
 * pollJob() transparently polls GET /api/jobs/{job_id} until done,
 * so all mutation hooks continue to resolve with their final payload types.
 * The FastAPI backend (src/agent_hum_crawler/api/) uses direct function calls
 * instead of subprocess — server auto-selects fastapi when installed.
 */

import type {
  OverviewResponse,
  ReportListItem,
  ReportDetail,
  SourceCheckResponse,
  CountrySourcesResponse,
  SystemInfoResponse,
  WorkbenchResponse,
  WorkbenchProfileStore,
  SAResponse,
  CliResult,
  DbCyclesResponse,
  DbEventsResponse,
  DbRawItemsResponse,
  DbFeedHealthResponse,
  ExtractionDiagnosticsResponse,
} from "@/types";
import type { ZodType } from "zod";
import {
  overviewResponseSchema,
  reportListResponseSchema,
  reportDetailSchema,
  sourceCheckResponseSchema,
  countrySourcesResponseSchema,
  systemInfoResponseSchema,
  workbenchResponseSchema,
  workbenchProfileStoreSchema,
  workbenchProfileStoreResponseSchema,
  saResponseSchema,
  cliResultSchema,
  healthResponseSchema,
  featureFlagUpdateResponseSchema,
  dbCyclesResponseSchema,
  dbEventsResponseSchema,
  dbRawItemsResponseSchema,
  dbFeedHealthResponseSchema,
  extractionDiagnosticsResponseSchema,
  jobQueuedSchema,
  jobStatusSchema,
} from "@/lib/schemas";

const API_BASE = "/api";

// ── Generic fetch helper ────────────────────────────────────

async function apiFetch<T>(
  path: string,
  options?: RequestInit,
  schema?: ZodType<T>,
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const method = options?.method ?? (options?.body ? "POST" : "GET");
  const headers: Record<string, string> = {};
  if (options?.body) {
    headers["Content-Type"] = "application/json";
  }

  if (import.meta.env.DEV) {
    console.group(`%c[API] ${method} ${path}`, "color:#6366f1;font-weight:bold");
    if (options?.body) {
      try { console.log("📤 Request body:", JSON.parse(options.body as string)); }
      catch { console.log("📤 Request body (raw):", options.body); }
    }
  }

  const res = await fetch(url, { ...options, headers });

  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    if (import.meta.env.DEV) {
      console.error(`❌ HTTP ${res.status}:`, text);
      console.groupEnd();
    }
    throw new Error(`API ${res.status}: ${text}`);
  }

  const json: unknown = await res.json();

  if (import.meta.env.DEV) {
    console.log(`✅ HTTP ${res.status} — raw JSON:`, json);
  }

  if (schema) {
    try {
      const parsed = schema.parse(json);
      if (import.meta.env.DEV) {
        console.log("🔍 Schema-parsed result:", parsed);
        console.groupEnd();
      }
      return parsed;
    } catch (err) {
      if (import.meta.env.DEV) {
        console.error("⚠️ Schema validation failed:", err);
        console.groupEnd();
      }
      throw err;
    }
  }

  if (import.meta.env.DEV) console.groupEnd();

  return json as T;
}

// ── Async job polling ───────────────────────────────────────

/**
 * Poll GET /api/jobs/{jobId} until the job is done or errors out.
 * Returns the typed *result* field from the job status response.
 *
 * Adaptive back-off (R16): polls start at 1 s, doubling each time up to a
 * configurable cap (default 10 s).  This halves request volume for long jobs
 * vs the previous fixed-interval approach.
 *
 * Cancellation: pass an AbortSignal via opts.signal to stop polling when the
 * caller navigates away or unmounts.
 *
 * @param jobId     Job token returned by a 202 POST endpoint.
 * @param schema    Optional Zod schema to validate the result payload.
 * @param opts      minIntervalMs, maxIntervalMs, timeoutMs, signal.
 */
async function pollJob<T>(
  jobId: string,
  schema?: ZodType<T>,
  opts?: {
    minIntervalMs?: number;
    maxIntervalMs?: number;
    timeoutMs?: number;
    signal?: AbortSignal;
  },
): Promise<T> {
  const minMs = opts?.minIntervalMs ?? 1_000;
  const maxMs = opts?.maxIntervalMs ?? 10_000;
  const timeoutMs = opts?.timeoutMs ?? 15 * 60 * 1_000;
  const deadline = Date.now() + timeoutMs;
  let currentInterval = minMs;

  while (Date.now() < deadline) {
    if (opts?.signal?.aborted) {
      throw new DOMException(`Job ${jobId} polling aborted`, "AbortError");
    }

    const status = await apiFetch(`/jobs/${jobId}`, undefined, jobStatusSchema);

    if (status.status === "done") {
      const raw = status.result;
      if (schema) return schema.parse(raw);
      return raw as T;
    }

    if (status.status === "error") {
      throw new Error(status.error ?? `Job ${jobId} failed`);
    }

    // Still queued or running — adaptive back-off wait
    await new Promise<void>((res, rej) => {
      const timer = setTimeout(res, currentInterval);
      opts?.signal?.addEventListener("abort", () => {
        clearTimeout(timer);
        rej(new DOMException(`Job ${jobId} polling aborted`, "AbortError"));
      }, { once: true });
    });

    // Double the interval, capped at maxMs
    currentInterval = Math.min(currentInterval * 2, maxMs);
  }

  throw new Error(`Job ${jobId} timed out after ${timeoutMs}ms`);
}

// ── GET endpoints ───────────────────────────────────────────

export async function fetchOverview(): Promise<OverviewResponse> {
  return apiFetch("/overview", undefined, overviewResponseSchema);
}

export async function fetchReports(): Promise<ReportListItem[]> {
  const data = await apiFetch("/reports", undefined, reportListResponseSchema);
  return data.reports;
}

export async function fetchReport(name: string): Promise<ReportDetail> {
  return apiFetch(`/reports/${encodeURIComponent(name)}`, undefined, reportDetailSchema);
}

export async function fetchSystemInfo(): Promise<SystemInfoResponse> {
  return apiFetch("/system-info", undefined, systemInfoResponseSchema);
}

export async function fetchCountrySources(): Promise<CountrySourcesResponse> {
  return apiFetch("/country-sources", undefined, countrySourcesResponseSchema);
}

export async function fetchWorkbenchProfiles(): Promise<WorkbenchProfileStore> {
  return apiFetch("/workbench-profiles", undefined, workbenchProfileStoreSchema);
}

export async function fetchHealth(): Promise<{ status: string }> {
  return apiFetch("/health", undefined, healthResponseSchema);
}

// ── POST endpoints ──────────────────────────────────────────

export interface RunCycleParams {
  countries: string;
  disaster_types: string;
  limit: number;
  max_age_days: number;
}

export async function runCycle(params: RunCycleParams): Promise<CliResult> {
  // POST returns 202 + job token; poll until the cycle finishes
  const job = await apiFetch("/run-cycle", {
    method: "POST",
    body: JSON.stringify(params),
  }, jobQueuedSchema);
  return pollJob<CliResult>(job.job_id, cliResultSchema);
}

export interface WriteReportParams {
  countries: string;
  disaster_types: string;
  max_age_days: number;
  country_min_events: number;
  max_per_connector: number;
  max_per_source: number;
  limit_cycles: number;
  limit_events: number;
  report_template: string;
  use_llm: boolean;
}

export async function writeReport(params: WriteReportParams): Promise<CliResult> {
  const job = await apiFetch("/write-report", {
    method: "POST",
    body: JSON.stringify(params),
  }, jobQueuedSchema);
  return pollJob<CliResult>(job.job_id, cliResultSchema);
}

export async function runSourceCheck(params: RunCycleParams): Promise<SourceCheckResponse> {
  const job = await apiFetch("/source-check", {
    method: "POST",
    body: JSON.stringify(params),
  }, jobQueuedSchema);
  return pollJob<SourceCheckResponse>(job.job_id, sourceCheckResponseSchema);
}

export interface WriteSAParams {
  countries: string;
  disaster_types: string;
  title: string;
  event_name: string;
  event_type: string;
  period: string;
  sa_template: string;
  limit_cycles: number;
  limit_events: number;
  max_age_days: number;
  use_llm: boolean;
  quality_gate: boolean;
}

export async function writeSA(params: WriteSAParams): Promise<SAResponse> {
  const job = await apiFetch("/write-situation-analysis", {
    method: "POST",
    body: JSON.stringify(params),
  }, jobQueuedSchema);
  return pollJob<SAResponse>(job.job_id, saResponseSchema);
}

export async function runWorkbench(
  profile: Record<string, unknown>
): Promise<WorkbenchResponse> {
  const job = await apiFetch("/report-workbench", {
    method: "POST",
    body: JSON.stringify(profile),
  }, jobQueuedSchema);
  return pollJob<WorkbenchResponse>(job.job_id, workbenchResponseSchema);
}

export async function saveWorkbenchProfile(
  name: string,
  profile: Record<string, unknown>
): Promise<WorkbenchProfileStore> {
  const data = await apiFetch(
    "/workbench-profiles/save",
    {
      method: "POST",
      body: JSON.stringify({ name, profile }),
    },
    workbenchProfileStoreResponseSchema,
  );
  return data.store;
}

export async function deleteWorkbenchProfile(
  name: string
): Promise<WorkbenchProfileStore> {
  const data = await apiFetch(
    "/workbench-profiles/delete",
    {
      method: "POST",
      body: JSON.stringify({ name }),
    },
    workbenchProfileStoreResponseSchema,
  );
  return data.store;
}

export interface RunPipelineParams {
  countries: string;
  disaster_types: string;
  report_title: string;
  sa_title: string;
  event_name: string;
  event_type: string;
  period: string;
  limit_cycles: number;
  limit_events: number;
  max_age_days: number;
  use_llm: boolean;
}

export async function runPipeline(params: RunPipelineParams): Promise<CliResult> {
  const job = await apiFetch("/run-pipeline", {
    method: "POST",
    body: JSON.stringify(params),
  }, jobQueuedSchema);
  return pollJob<CliResult>(job.job_id, cliResultSchema);
}

export async function rerunLastWorkbench(): Promise<WorkbenchResponse> {
  const job = await apiFetch("/report-workbench/rerun-last", {
    method: "POST",
  }, jobQueuedSchema);
  return pollJob<WorkbenchResponse>(job.job_id, workbenchResponseSchema);
}

/** Toggle a single feature flag on or off. */
export async function updateFeatureFlag(
  flag: string,
  enabled: boolean,
): Promise<{ feature_flags: Record<string, boolean> }> {
  return apiFetch("/feature-flags", {
    method: "POST",
    body: JSON.stringify({ flag, enabled }),
  }, featureFlagUpdateResponseSchema);
}

// ── Database endpoints ──────────────────────────────────────

export async function fetchDbCycles(limit = 50): Promise<DbCyclesResponse> {
  return apiFetch(`/db/cycles?limit=${limit}`, undefined, dbCyclesResponseSchema);
}

export interface DbEventsParams {
  limit?: number;
  country?: string;
  disaster_type?: string;
}

export async function fetchDbEvents(params: DbEventsParams = {}): Promise<DbEventsResponse> {
  const qs = new URLSearchParams();
  if (params.limit) qs.set("limit", String(params.limit));
  if (params.country) qs.set("country", params.country);
  if (params.disaster_type) qs.set("disaster_type", params.disaster_type);
  const query = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch(`/db/events${query}`, undefined, dbEventsResponseSchema);
}

export async function fetchDbRawItems(limit = 100): Promise<DbRawItemsResponse> {
  return apiFetch(`/db/raw-items?limit=${limit}`, undefined, dbRawItemsResponseSchema);
}

export async function fetchDbFeedHealth(limit = 100): Promise<DbFeedHealthResponse> {
  return apiFetch(`/db/feed-health?limit=${limit}`, undefined, dbFeedHealthResponseSchema);
}

export interface ExtractionDiagnosticsParams {
  limit_cycles?: number;
  connector?: string;
}

export async function fetchExtractionDiagnostics(
  params: ExtractionDiagnosticsParams = {},
): Promise<ExtractionDiagnosticsResponse> {
  const qs = new URLSearchParams();
  if (params.limit_cycles) qs.set("limit_cycles", String(params.limit_cycles));
  if (params.connector) qs.set("connector", params.connector);
  const query = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch(`/db/extraction-diagnostics${query}`, undefined, extractionDiagnosticsResponseSchema);
}
