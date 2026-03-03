/**
 * Project Phoenix — API Client
 * Type-safe wrapper around the existing dashboard API (port 8788).
 * Zod schemas validate all responses at runtime.
 * In Phase 7 this will be migrated to FastAPI endpoints.
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
} from "@/lib/schemas";

const API_BASE = "/api";

// ── Generic fetch helper ────────────────────────────────────

async function apiFetch<T>(
  path: string,
  options?: RequestInit,
  schema?: ZodType<T>,
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const headers: Record<string, string> = {};
  if (options?.body) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(url, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    throw new Error(`API ${res.status}: ${text}`);
  }

  const json: unknown = await res.json();

  if (schema) {
    try {
      return schema.parse(json);
    } catch (err) {
      if (import.meta.env.DEV) {
        console.error(`[Phoenix] Schema validation failed for ${path}:`, err);
      }
      throw err;
    }
  }

  return json as T;
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
  return apiFetch("/run-cycle", {
    method: "POST",
    body: JSON.stringify(params),
  }, cliResultSchema);
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
  return apiFetch("/write-report", {
    method: "POST",
    body: JSON.stringify(params),
  }, cliResultSchema);
}

export async function runSourceCheck(params: RunCycleParams): Promise<SourceCheckResponse> {
  return apiFetch("/source-check", {
    method: "POST",
    body: JSON.stringify(params),
  }, sourceCheckResponseSchema);
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
  return apiFetch("/write-situation-analysis", {
    method: "POST",
    body: JSON.stringify(params),
  }, saResponseSchema);
}

export async function runWorkbench(
  profile: Record<string, unknown>
): Promise<WorkbenchResponse> {
  return apiFetch("/report-workbench", {
    method: "POST",
    body: JSON.stringify(profile),
  }, workbenchResponseSchema);
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
  return apiFetch("/run-pipeline", {
    method: "POST",
    body: JSON.stringify(params),
  }, cliResultSchema);
}

export async function rerunLastWorkbench(): Promise<WorkbenchResponse> {
  return apiFetch("/report-workbench/rerun-last", {
    method: "POST",
  }, workbenchResponseSchema);
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
