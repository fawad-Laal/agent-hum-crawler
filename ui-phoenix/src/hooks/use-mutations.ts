/**
 * Project Phoenix — TanStack Query Mutation Hooks
 * Type-safe mutation hooks for all POST endpoints.
 * Handles cache invalidation and error propagation.
 * All invalidation keys sourced from lib/query-keys.ts.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  runCycle,
  writeReport,
  runSourceCheck,
  writeSA,
  runWorkbench,
  saveWorkbenchProfile,
  deleteWorkbenchProfile,
  runPipeline,
  rerunLastWorkbench,
} from "@/lib/api";
import type {
  CliResult,
  SourceCheckResponse,
  SAResponse,
  WorkbenchResponse,
  WorkbenchProfileStore,
} from "@/types";
import type { RunCycleParams, WriteReportParams, WriteSAParams, RunPipelineParams } from "@/lib/api";
import { QUERY_KEYS } from "@/lib/query-keys";

/** Trigger a collection cycle and refresh dashboard data on success. */
export function useRunCycle() {
  const queryClient = useQueryClient();

  return useMutation<CliResult, Error, RunCycleParams>({
    mutationFn: runCycle,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.overview });
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.reports });
    },
  });
}

/** Generate a report and refresh report listing on success. */
export function useWriteReport() {
  const queryClient = useQueryClient();

  return useMutation<CliResult, Error, WriteReportParams>({
    mutationFn: writeReport,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.reports });
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.overview });
    },
  });
}

/** Run a source check — result is returned directly, no cache invalidation. */
export function useRunSourceCheck() {
  return useMutation<SourceCheckResponse, Error, RunCycleParams>({
    mutationFn: runSourceCheck,
  });
}

/** Generate a situation analysis and refresh report listing. */
export function useWriteSA() {
  const queryClient = useQueryClient();

  return useMutation<SAResponse, Error, WriteSAParams>({
    mutationFn: writeSA,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.reports });
    },
  });
}

/** Run full pipeline (Cycle → Report → SA) and refresh dashboard. */
export function useRunPipeline() {
  const queryClient = useQueryClient();

  return useMutation<CliResult, Error, RunPipelineParams>({
    mutationFn: runPipeline,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.overview });
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.reports });
    },
  });
}

/** Run the report workbench with a custom profile. */
export function useRunWorkbench() {
  return useMutation<WorkbenchResponse, Error, Record<string, unknown>>({
    mutationFn: runWorkbench,
  });
}

/** Re-run the workbench with the last-used profile. */
export function useRerunLastWorkbench() {
  return useMutation<WorkbenchResponse, Error, void>({
    mutationFn: rerunLastWorkbench,
  });
}

/** Save a named workbench profile preset. */
export function useSaveWorkbenchProfile() {
  const queryClient = useQueryClient();

  return useMutation<
    WorkbenchProfileStore,
    Error,
    { name: string; profile: Record<string, unknown> }
  >({
    mutationFn: ({ name, profile }) => saveWorkbenchProfile(name, profile),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.workbenchProfiles });
    },
  });
}

/** Delete a workbench profile preset by name. */
export function useDeleteWorkbenchProfile() {
  const queryClient = useQueryClient();

  return useMutation<WorkbenchProfileStore, Error, string>({
    mutationFn: deleteWorkbenchProfile,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.workbenchProfiles });
    },
  });
}
