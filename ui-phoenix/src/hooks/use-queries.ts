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
} from "@/lib/api";
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
