/**
 * Project Phoenix — TanStack Query Mutation Hooks
 * Type-safe mutation hooks for all POST endpoints.
 * Handles cache invalidation and error propagation.
 * All invalidation keys sourced from lib/query-keys.ts.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
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
  updateFeatureFlag,
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
    onMutate: (variables) => {
      console.group("%c[RunCycle] ▶ Starting cycle", "color:#10b981;font-weight:bold");
      console.log("📋 Params:", variables);
    },
    onSuccess: (data, variables) => {
      console.log("✅ Success — full response:", data);
      console.log("   status:", data.status);
      console.log("   params used:", variables);
      console.groupEnd();
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.overview });
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.reports });
      toast.success("Collection cycle completed", { description: `Status: ${data.status}` });
    },
    onError: (err, variables) => {
      console.error("❌ Error:", err.message);
      console.error("   params used:", variables);
      console.groupEnd();
      toast.error("Cycle failed", { description: err.message });
    },
  });
}

/** Generate a report and refresh report listing on success. */
export function useWriteReport() {
  const queryClient = useQueryClient();

  return useMutation<CliResult, Error, WriteReportParams>({
    mutationFn: writeReport,
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.reports });
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.overview });
      toast.success("Report generated", { description: `Status: ${data.status}` });
    },
    onError: (err) => {
      toast.error("Report failed", { description: err.message });
    },
  });
}

/** Run a source check — result is returned directly, no cache invalidation. */
export function useRunSourceCheck() {
  return useMutation<SourceCheckResponse, Error, RunCycleParams>({
    mutationFn: runSourceCheck,
    onSuccess: (data) => {
      const total = data.total_sources ?? 0;
      const working = data.working_sources ?? 0;
      if (total === 0) {
        toast.warning("No sources found — check your country and feed configuration");
      } else {
        toast[working === total ? "success" : "warning"](
          `Source check: ${working}/${total} sources working`
        );
      }
    },
    onError: (err) => {
      toast.error("Source check failed", { description: err.message });
    },
  });
}

/** Generate a situation analysis and refresh report listing. */
export function useWriteSA() {
  const queryClient = useQueryClient();

  return useMutation<SAResponse, Error, WriteSAParams>({
    mutationFn: writeSA,
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.reports });
      toast.success("Situation Analysis generated", {
        description: data.output_file ? `Saved: ${data.output_file.replace(/^.*[\/\\]/, "")}` : undefined,
      });
    },
    onError: (err) => {
      toast.error("SA generation failed", { description: err.message });
    },
  });
}

/** Run full pipeline (Cycle → Report → SA) and refresh dashboard. */
export function useRunPipeline() {
  const queryClient = useQueryClient();

  return useMutation<CliResult, Error, RunPipelineParams>({
    mutationFn: runPipeline,
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.overview });
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.reports });
      toast.success("Full pipeline completed", { description: `Status: ${data.status}` });
    },
    onError: (err) => {
      toast.error("Pipeline failed", { description: err.message });
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

/** Toggle a feature flag and refresh the overview (source of truth). */
export function useUpdateFeatureFlag() {
  const queryClient = useQueryClient();

  return useMutation<
    { feature_flags: Record<string, boolean> },
    Error,
    { flag: string; enabled: boolean }
  >({
    mutationFn: ({ flag, enabled }) => updateFeatureFlag(flag, enabled),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.overview });
    },
  });
}
