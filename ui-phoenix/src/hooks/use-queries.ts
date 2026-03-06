/**
 * Project Phoenix — TanStack Query Hooks
 * Type-safe data fetching hooks for each API endpoint.
 * All keys sourced from lib/query-keys.ts.
 */

import { useQuery } from "@tanstack/react-query";
import {
  fetchOverview,
  fetchReports,
  fetchReport,
  fetchSystemInfo,
  fetchCountrySources,
  fetchWorkbenchProfiles,
  fetchHealth,
  fetchDbCycles,
  fetchDbEvents,
  fetchDbRawItems,
  fetchDbFeedHealth,
  fetchExtractionDiagnostics,
} from "@/lib/api";
import type { DbEventsParams, ExtractionDiagnosticsParams } from "@/lib/api";
import { QUERY_KEYS } from "@/lib/query-keys";

/** Dashboard overview (KPIs, trends, hardening, cycles) */
export function useOverview() {
  return useQuery({
    queryKey: QUERY_KEYS.overview,
    queryFn: fetchOverview,
    refetchInterval: 30_000, // auto-refresh every 30s
    staleTime: 10_000,
  });
}

/** Report listing */
export function useReports() {
  return useQuery({
    queryKey: QUERY_KEYS.reports,
    queryFn: fetchReports,
    staleTime: 15_000,
  });
}

/** Single report content */
export function useReport(name: string | null) {
  return useQuery({
    queryKey: QUERY_KEYS.report(name ?? ""),
    queryFn: () => fetchReport(name ?? ""),
    enabled: !!name,
    staleTime: 60_000,
  });
}

/** System info (Python version, Rust availability, disaster types) */
export function useSystemInfo() {
  return useQuery({
    queryKey: QUERY_KEYS.systemInfo,
    queryFn: fetchSystemInfo,
    staleTime: 300_000, // rarely changes
  });
}

/** Country ↔ source feed configuration */
export function useCountrySources() {
  return useQuery({
    queryKey: QUERY_KEYS.countrySources,
    queryFn: fetchCountrySources,
    staleTime: 60_000,
  });
}

/** Workbench profile presets */
export function useWorkbenchProfiles() {
  return useQuery({
    queryKey: QUERY_KEYS.workbenchProfiles,
    queryFn: fetchWorkbenchProfiles,
    staleTime: 30_000,
  });
}

/** Backend health check */
export function useHealth() {
  return useQuery({
    queryKey: QUERY_KEYS.health,
    queryFn: fetchHealth,
    refetchInterval: 60_000,
    staleTime: 15_000,
  });
}

// ── Database hooks ──────────────────────────────────────────

/** Cycle runs stored in the monitoring DB */
export function useDbCycles(limit = 50) {
  return useQuery({
    queryKey: QUERY_KEYS.dbCycles(limit),
    queryFn: () => fetchDbCycles(limit),
    staleTime: 10_000,
  });
}

/** Events stored in the monitoring DB, optionally filtered */
export function useDbEvents(params: DbEventsParams = {}) {
  const limit = params.limit ?? 100;
  return useQuery({
    queryKey: QUERY_KEYS.dbEvents(params),
    queryFn: () => fetchDbEvents(params),
    staleTime: 10_000,
    enabled: true,
  });
}

/** Raw items stored in the monitoring DB */
export function useDbRawItems(limit = 100) {
  return useQuery({
    queryKey: QUERY_KEYS.dbRawItems(limit),
    queryFn: () => fetchDbRawItems(limit),
    staleTime: 30_000,
  });
}

/** Feed health records */
export function useDbFeedHealth(limit = 100) {
  return useQuery({
    queryKey: QUERY_KEYS.dbFeedHealth(limit),
    queryFn: () => fetchDbFeedHealth(limit),
    staleTime: 30_000,
  });
}

/** Extraction telemetry diagnostics (Phase 9.5) */
export function useExtractionDiagnostics(params: ExtractionDiagnosticsParams = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.extractionDiagnostics(params),
    queryFn: () => fetchExtractionDiagnostics(params),
    staleTime: 30_000,
  });
}
