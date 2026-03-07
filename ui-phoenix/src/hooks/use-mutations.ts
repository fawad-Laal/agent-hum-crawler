/**
 * Project Phoenix — TanStack Query Mutation Hooks
 * Type-safe mutation hooks for all POST endpoints.
 * Handles cache invalidation and error propagation.
 * All invalidation keys sourced from lib/query-keys.ts.
 *
 * Phase 8: loading toasts (Sonner) + global jobs store registration so
 * GlobalJobBadge in the header shows an animated spinner while any
 * long-running mutation is in flight.
 */

import { useRef } from "react";
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
import { useJobsStore } from "@/stores/jobs-store";

// ── Stable toast IDs (one per mutation type — semaphore ensures no overlap) ────
const TOAST = {
  cycle: "toast-run-cycle",
  report: "toast-write-report",
  sourceCheck: "toast-source-check",
  sa: "toast-write-sa",
  pipeline: "toast-run-pipeline",
  featureFlag: "toast-feature-flag",
} as const;

/** Trigger a collection cycle and refresh dashboard data on success. */
export function useRunCycle() {
  const queryClient = useQueryClient();
  const { addJob, removeJob } = useJobsStore();
  const activeJobIdRef = useRef<string | null>(null);

  return useMutation<CliResult, Error, RunCycleParams>({
    mutationFn: (params) =>
      runCycle(params, (id) => {
        activeJobIdRef.current = id;
        addJob(id, "Running cycle");
      }),
    onMutate: (variables) => {
      console.group("%c[RunCycle] ▶ Starting cycle", "color:#10b981;font-weight:bold");
      console.log("📋 Params:", variables);
      toast.loading("Running collection cycle…", { id: TOAST.cycle });
    },
    onSuccess: (data, variables) => {
      console.log("✅ Success — full response:", data);
      console.log("   status:", data.status);
      console.log("   params used:", variables);
      console.groupEnd();
      if (activeJobIdRef.current) removeJob(activeJobIdRef.current);
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.overview });
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.reports });
      toast.success("Collection cycle completed", { id: TOAST.cycle, description: `Status: ${data.status}` });
    },
    onError: (err, variables) => {
      console.error("❌ Error:", err.message);
      console.error("   params used:", variables);
      console.groupEnd();
      if (activeJobIdRef.current) removeJob(activeJobIdRef.current);
      toast.error("Cycle failed", { id: TOAST.cycle, description: err.message });
    },
  });
}

/** Generate a report and refresh report listing on success. */
export function useWriteReport() {
  const queryClient = useQueryClient();
  const { addJob, removeJob } = useJobsStore();
  const activeJobIdRef = useRef<string | null>(null);

  return useMutation<CliResult, Error, WriteReportParams>({
    mutationFn: (params) =>
      writeReport(params, (id) => {
        activeJobIdRef.current = id;
        addJob(id, "Generating report");
      }),
    onMutate: () => {
      toast.loading("Generating report…", { id: TOAST.report });
    },
    onSuccess: (data) => {
      if (activeJobIdRef.current) removeJob(activeJobIdRef.current);
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.reports });
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.overview });
      toast.success("Report generated", { id: TOAST.report, description: `Status: ${data.status}` });
    },
    onError: (err) => {
      if (activeJobIdRef.current) removeJob(activeJobIdRef.current);
      toast.error("Report failed", { id: TOAST.report, description: err.message });
    },
  });
}

/** Run a source check — result is returned directly, no cache invalidation. */
export function useRunSourceCheck() {
  const { addJob, removeJob } = useJobsStore();
  const activeJobIdRef = useRef<string | null>(null);

  return useMutation<SourceCheckResponse, Error, RunCycleParams>({
    mutationFn: (params) =>
      runSourceCheck(params, (id) => {
        activeJobIdRef.current = id;
        addJob(id, "Checking sources");
      }),
    onMutate: () => {
      toast.loading("Checking sources…", { id: TOAST.sourceCheck });
    },
    onSuccess: (data) => {
      if (activeJobIdRef.current) removeJob(activeJobIdRef.current);
      const total = data.total_sources ?? 0;
      const working = data.working_sources ?? 0;
      if (total === 0) {
        toast.warning("No sources found — check your country and feed configuration", {
          id: TOAST.sourceCheck,
        });
      } else {
        toast[working === total ? "success" : "warning"](
          `Source check: ${working}/${total} sources working`,
          { id: TOAST.sourceCheck },
        );
      }
    },
    onError: (err) => {
      if (activeJobIdRef.current) removeJob(activeJobIdRef.current);
      toast.error("Source check failed", { id: TOAST.sourceCheck, description: err.message });
    },
  });
}

/** Generate a situation analysis and refresh report listing. */
export function useWriteSA() {
  const queryClient = useQueryClient();
  const { addJob, removeJob } = useJobsStore();
  const activeJobIdRef = useRef<string | null>(null);

  return useMutation<SAResponse, Error, WriteSAParams>({
    mutationFn: (params) =>
      writeSA(params, (id) => {
        activeJobIdRef.current = id;
        addJob(id, "Generating SA");
      }),
    onMutate: () => {
      toast.loading("Generating Situation Analysis…", { id: TOAST.sa });
    },
    onSuccess: (data) => {
      if (activeJobIdRef.current) removeJob(activeJobIdRef.current);
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.reports });
      toast.success("Situation Analysis generated", {
        id: TOAST.sa,
        description: data.output_file ? `Saved: ${data.output_file.replace(/^.*[\/\\]/, "")}` : undefined,
      });
    },
    onError: (err) => {
      if (activeJobIdRef.current) removeJob(activeJobIdRef.current);
      toast.error("SA generation failed", { id: TOAST.sa, description: err.message });
    },
  });
}

/** Run full pipeline (Cycle → Report → SA) and refresh dashboard. */
export function useRunPipeline() {
  const queryClient = useQueryClient();
  const { addJob, removeJob } = useJobsStore();
  const activeJobIdRef = useRef<string | null>(null);

  return useMutation<CliResult, Error, RunPipelineParams>({
    mutationFn: (params) =>
      runPipeline(params, (id) => {
        activeJobIdRef.current = id;
        addJob(id, "Running pipeline");
      }),
    onMutate: () => {
      toast.loading("Running full pipeline…", { id: TOAST.pipeline });
    },
    onSuccess: (data) => {
      if (activeJobIdRef.current) removeJob(activeJobIdRef.current);
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.overview });
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.reports });
      toast.success("Full pipeline completed", { id: TOAST.pipeline, description: `Status: ${data.status}` });
    },
    onError: (err) => {
      if (activeJobIdRef.current) removeJob(activeJobIdRef.current);
      toast.error("Pipeline failed", { id: TOAST.pipeline, description: err.message });
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
    onMutate: ({ flag }) => {
      toast.loading(`Updating ${flag}…`, { id: TOAST.featureFlag });
    },
    onSuccess: (_, { flag, enabled }) => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.overview });
      toast.success(`${flag.replace(/_/g, " ")} ${enabled ? "enabled" : "disabled"}`, {
        id: TOAST.featureFlag,
      });
    },
    onError: (err, { flag }) => {
      toast.error(`Failed to toggle ${flag}: ${err.message}`, { id: TOAST.featureFlag });
    },
  });
}
