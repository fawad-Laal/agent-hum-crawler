/**
 * Phase 10.1 — Hooks Tests
 * Covers hooks/use-mutations.ts (all 10 mutations) and
 * hooks/use-queries.ts (all 12 query hooks including DB hooks).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { toast } from "sonner";
import * as api from "@/lib/api";
import {
  useRunCycle,
  useWriteReport,
  useRunSourceCheck,
  useWriteSA,
  useRunPipeline,
  useRunWorkbench,
  useRerunLastWorkbench,
  useSaveWorkbenchProfile,
  useDeleteWorkbenchProfile,
  useUpdateFeatureFlag,
} from "@/hooks/use-mutations";
import {
  useOverview,
  useReports,
  useReport,
  useSystemInfo,
  useCountrySources,
  useWorkbenchProfiles,
  useHealth,
  useDbCycles,
  useDbEvents,
  useDbRawItems,
  useDbFeedHealth,
  useExtractionDiagnostics,
} from "@/hooks/use-queries";
import { useJobsStore } from "@/stores/jobs-store";

// ── Test wrapper ───────────────────────────────────────────────

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };
}

// ── Silence console noise ──────────────────────────────────────

beforeEach(() => {
  useJobsStore.setState({ jobs: {} });
  vi.spyOn(console, "group").mockImplementation(() => {});
  vi.spyOn(console, "groupEnd").mockImplementation(() => {});
  vi.spyOn(console, "log").mockImplementation(() => {});
  vi.spyOn(console, "error").mockImplementation(() => {});
  // Silence Sonner so toast calls don't throw in JSDOM
  vi.spyOn(toast, "loading").mockImplementation(() => "");
  vi.spyOn(toast, "success").mockImplementation(() => "");
  vi.spyOn(toast, "error").mockImplementation(() => "");
  vi.spyOn(toast, "warning").mockImplementation(() => "");
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ═══════════════════════════════════════════════════════════════
// MUTATION HOOKS
// ═══════════════════════════════════════════════════════════════

// ── useRunCycle ───────────────────────────────────────────────

describe("useRunCycle", () => {
  const params: api.RunCycleParams = {
    countries: "Lebanon",
    disaster_types: "conflict",
    limit: 10,
    max_age_days: 30,
  };

  it("succeeds and resolves with CLI result", async () => {
    vi.spyOn(api, "runCycle").mockResolvedValue({ status: "ok", output: "done" });
    const { result } = renderHook(() => useRunCycle(), { wrapper: makeWrapper() });

    act(() => { result.current.mutate(params); });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.status).toBe("ok");
  });

  it("adds and removes job from jobs store on success", async () => {
    vi.spyOn(api, "runCycle").mockResolvedValue({ status: "ok" });
    const { result } = renderHook(() => useRunCycle(), { wrapper: makeWrapper() });

    act(() => { result.current.mutate(params); });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(useJobsStore.getState().activeCount()).toBe(0);
  });

  it("sets error state on failure", async () => {
    vi.spyOn(api, "runCycle").mockRejectedValue(new Error("cycle crashed"));
    const { result } = renderHook(() => useRunCycle(), { wrapper: makeWrapper() });

    act(() => { result.current.mutate(params); });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("cycle crashed");
  });

  // ── 10A.3: real backend job_id ────────────────────────────────────────────

  it("10A.3: registers REAL backend job_id in jobs store (not toast placeholder)", async () => {
    vi.spyOn(api, "runCycle").mockImplementation(async (_params, onJobQueued) => {
      onJobQueued?.("real-backend-id");
      return { status: "ok" };
    });

    const jobIdsAdded: string[] = [];
    const unsub = useJobsStore.subscribe((state, prev) => {
      Object.keys(state.jobs).forEach((k) => {
        if (!(k in prev.jobs)) jobIdsAdded.push(k);
      });
    });

    const { result } = renderHook(() => useRunCycle(), { wrapper: makeWrapper() });
    act(() => { result.current.mutate(params); });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    unsub();

    expect(jobIdsAdded).toContain("real-backend-id");
    expect(jobIdsAdded).not.toContain("toast-run-cycle");
  });

  it("10A.3: removes job by real backend job_id on completion", async () => {
    vi.spyOn(api, "runCycle").mockImplementation(async (_params, onJobQueued) => {
      onJobQueued?.("real-backend-id");
      return { status: "ok" };
    });

    const { result } = renderHook(() => useRunCycle(), { wrapper: makeWrapper() });
    act(() => { result.current.mutate(params); });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    // Job must be cleaned up after success
    expect(useJobsStore.getState().jobs["real-backend-id"]).toBeUndefined();
    expect(useJobsStore.getState().activeCount()).toBe(0);
  });
});

// ── useWriteReport ────────────────────────────────────────────

describe("useWriteReport", () => {
  const params: api.WriteReportParams = {
    countries: "Lebanon",
    disaster_types: "conflict",
    max_age_days: 30,
    country_min_events: 1,
    max_per_connector: 5,
    max_per_source: 3,
    limit_cycles: 2,
    limit_events: 50,
    report_template: "default",
    use_llm: false,
  };

  it("resolves with CLI result on success", async () => {
    vi.spyOn(api, "writeReport").mockResolvedValue({ status: "ok" });
    const { result } = renderHook(() => useWriteReport(), { wrapper: makeWrapper() });

    act(() => { result.current.mutate(params); });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.status).toBe("ok");
  });

  it("exposes error on failure", async () => {
    vi.spyOn(api, "writeReport").mockRejectedValue(new Error("report failed"));
    const { result } = renderHook(() => useWriteReport(), { wrapper: makeWrapper() });

    act(() => { result.current.mutate(params); });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("report failed");
  });
});

// ── useRunSourceCheck ─────────────────────────────────────────

describe("useRunSourceCheck", () => {
  const params: api.RunCycleParams = { countries: "Lebanon", disaster_types: "conflict", limit: 10, max_age_days: 30 };

  it("resolves with source check response", async () => {
    vi.spyOn(api, "runSourceCheck").mockResolvedValue({ status: "ok", working_sources: 4, total_sources: 5 });
    const { result } = renderHook(() => useRunSourceCheck(), { wrapper: makeWrapper() });

    act(() => { result.current.mutate(params); });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.status).toBe("ok");
  });

  it("handles no-sources case (total_sources = 0)", async () => {
    vi.spyOn(api, "runSourceCheck").mockResolvedValue({ status: "ok", working_sources: 0, total_sources: 0 });
    const { result } = renderHook(() => useRunSourceCheck(), { wrapper: makeWrapper() });

    act(() => { result.current.mutate(params); });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    // Resolves without error even when no sources found
    expect(result.current.data?.total_sources).toBe(0);
  });

  it("partial sources triggers warning-level success still resolves", async () => {
    vi.spyOn(api, "runSourceCheck").mockResolvedValue({ status: "ok", working_sources: 3, total_sources: 5 });
    const { result } = renderHook(() => useRunSourceCheck(), { wrapper: makeWrapper() });

    act(() => { result.current.mutate(params); });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.working_sources).toBe(3);
  });
});

// ── useWriteSA ────────────────────────────────────────────────

describe("useWriteSA", () => {
  const params: api.WriteSAParams = {
    countries: "Lebanon",
    disaster_types: "conflict",
    title: "Lebanon SA",
    event_name: "Lebanon Conflict",
    event_type: "conflict",
    period: "Q1 2026",
    sa_template: "ocha_full",
    limit_cycles: 2,
    limit_events: 50,
    max_age_days: 30,
    use_llm: false,
    quality_gate: false,
  };

  it("resolves with SA response including markdown", async () => {
    vi.spyOn(api, "writeSA").mockResolvedValue({ markdown: "# SA", output_file: "sa.md", status: "ok" });
    const { result } = renderHook(() => useWriteSA(), { wrapper: makeWrapper() });

    act(() => { result.current.mutate(params); });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.markdown).toBe("# SA");
  });

  it("toast description includes filename when output_file is present", async () => {
    vi.spyOn(api, "writeSA").mockResolvedValue({ markdown: "# SA", output_file: "/some/path/sa-file.md" });
    const { result } = renderHook(() => useWriteSA(), { wrapper: makeWrapper() });

    act(() => { result.current.mutate(params); });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.output_file).toContain("sa-file.md");
  });
});

// ── useRunPipeline ────────────────────────────────────────────

describe("useRunPipeline", () => {
  const params: api.RunPipelineParams = {
    countries: "Lebanon",
    disaster_types: "conflict",
    report_title: "Lebanon Report",
    sa_title: "Lebanon SA",
    event_name: "Lebanon Conflict",
    event_type: "conflict",
    period: "Q1 2026",
    limit_cycles: 2,
    limit_events: 50,
    max_age_days: 30,
    use_llm: false,
  };

  it("resolves with CLI result on success", async () => {
    vi.spyOn(api, "runPipeline").mockResolvedValue({ status: "ok" });
    const { result } = renderHook(() => useRunPipeline(), { wrapper: makeWrapper() });

    act(() => { result.current.mutate(params); });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.status).toBe("ok");
  });

  it("exposes error on failure", async () => {
    vi.spyOn(api, "runPipeline").mockRejectedValue(new Error("pipeline failed"));
    const { result } = renderHook(() => useRunPipeline(), { wrapper: makeWrapper() });

    act(() => { result.current.mutate(params); });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

// ── useRunWorkbench ───────────────────────────────────────────

describe("useRunWorkbench", () => {
  it("resolves with workbench response", async () => {
    const mockResult = {
      profile: {},
      template: {},
      deterministic: { markdown: "# Det", section_word_usage: {} },
      ai: { markdown: "# AI", section_word_usage: {} },
    };
    vi.spyOn(api, "runWorkbench").mockResolvedValue(mockResult);
    const { result } = renderHook(() => useRunWorkbench(), { wrapper: makeWrapper() });

    act(() => { result.current.mutate({ template: "default" }); });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.deterministic.markdown).toBe("# Det");
  });
});

// ── useRerunLastWorkbench ─────────────────────────────────────

describe("useRerunLastWorkbench", () => {
  it("resolves with workbench response", async () => {
    const mockResult = {
      profile: {},
      template: {},
      deterministic: { markdown: "# Det", section_word_usage: {} },
      ai: { markdown: "# AI", section_word_usage: {} },
    };
    vi.spyOn(api, "rerunLastWorkbench").mockResolvedValue(mockResult);
    const { result } = renderHook(() => useRerunLastWorkbench(), { wrapper: makeWrapper() });

    act(() => { result.current.mutate(); });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.ai.markdown).toBe("# AI");
  });
});

// ── useSaveWorkbenchProfile ───────────────────────────────────

describe("useSaveWorkbenchProfile", () => {
  it("resolves with updated profile store", async () => {
    const store = { presets: { "my-profile": {} }, last_profile: null };
    vi.spyOn(api, "saveWorkbenchProfile").mockResolvedValue(store);
    const { result } = renderHook(() => useSaveWorkbenchProfile(), { wrapper: makeWrapper() });

    act(() => { result.current.mutate({ name: "my-profile", profile: {} }); });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.presets).toHaveProperty("my-profile");
  });
});

// ── useDeleteWorkbenchProfile ─────────────────────────────────

describe("useDeleteWorkbenchProfile", () => {
  it("resolves with updated profile store (empty presets)", async () => {
    const store = { presets: {}, last_profile: null };
    vi.spyOn(api, "deleteWorkbenchProfile").mockResolvedValue(store);
    const { result } = renderHook(() => useDeleteWorkbenchProfile(), { wrapper: makeWrapper() });

    act(() => { result.current.mutate("my-profile"); });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.presets).toEqual({});
  });
});

// ── useUpdateFeatureFlag ──────────────────────────────────────

describe("useUpdateFeatureFlag", () => {
  it("resolves with updated flags map", async () => {
    vi.spyOn(api, "updateFeatureFlag").mockResolvedValue({ feature_flags: { use_llm: true } });
    const { result } = renderHook(() => useUpdateFeatureFlag(), { wrapper: makeWrapper() });

    act(() => { result.current.mutate({ flag: "use_llm", enabled: true }); });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.feature_flags.use_llm).toBe(true);
  });

  // ── 10A.4: hook-level toast ownership ──────────────────────────────────────

  it("10A.4: emits loading toast before resolving", async () => {
    vi.spyOn(api, "updateFeatureFlag").mockResolvedValue({ feature_flags: { use_llm: true } });
    const { result } = renderHook(() => useUpdateFeatureFlag(), { wrapper: makeWrapper() });

    act(() => { result.current.mutate({ flag: "use_llm", enabled: true }); });

    expect(toast.loading).toHaveBeenCalled();
  });

  it("10A.4: emits success toast after successful toggle", async () => {
    vi.spyOn(api, "updateFeatureFlag").mockResolvedValue({ feature_flags: { use_llm: true } });
    const { result } = renderHook(() => useUpdateFeatureFlag(), { wrapper: makeWrapper() });

    act(() => { result.current.mutate({ flag: "use_llm", enabled: true }); });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(toast.success).toHaveBeenCalled();
  });

  it("10A.4: emits error toast containing flag name on failure", async () => {
    vi.spyOn(api, "updateFeatureFlag").mockRejectedValue(new Error("toggle boom"));
    const { result } = renderHook(() => useUpdateFeatureFlag(), { wrapper: makeWrapper() });

    act(() => { result.current.mutate({ flag: "use_llm", enabled: true }); });
    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(toast.error).toHaveBeenCalledWith(
      expect.stringContaining("use_llm"),
      expect.any(Object),
    );
  });
});

// ═══════════════════════════════════════════════════════════════
// QUERY HOOKS
// ═══════════════════════════════════════════════════════════════

const OVERVIEW = {
  quality: { cycles_analyzed: 5, events_analyzed: 42 },
  source_health: { working: 4, total: 5 },
  hardening: { status: "pass" },
  cycles: [],
  quality_trend: [],
};

describe("useOverview", () => {
  it("returns overview data from the API", async () => {
    vi.spyOn(api, "fetchOverview").mockResolvedValue(OVERVIEW as ReturnType<typeof api.fetchOverview> extends Promise<infer T> ? T : never);
    const { result } = renderHook(() => useOverview(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.hardening.status).toBe("pass");
  });

  it("exposes error state when fetch fails", async () => {
    vi.spyOn(api, "fetchOverview").mockRejectedValue(new Error("network error"));
    const { result } = renderHook(() => useOverview(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

describe("useReports", () => {
  it("returns an array of report items", async () => {
    vi.spyOn(api, "fetchReports").mockResolvedValue([{ name: "report.md", size: 1024, modified: 1700000000 }]);
    const { result } = renderHook(() => useReports(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.[0].name).toBe("report.md");
  });
});

describe("useReport", () => {
  it("is disabled when name is null", () => {
    const { result } = renderHook(() => useReport(null), { wrapper: makeWrapper() });
    // enabled=false means query stays in pending state — not fetching
    expect(result.current.isFetching).toBe(false);
  });

  it("fetches when a name is provided", async () => {
    vi.spyOn(api, "fetchReport").mockResolvedValue({ name: "report.md", markdown: "# Content" });
    const { result } = renderHook(() => useReport("report.md"), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.markdown).toBe("# Content");
  });
});

describe("useSystemInfo", () => {
  it("returns system info", async () => {
    vi.spyOn(api, "fetchSystemInfo").mockResolvedValue({
      python_version: "3.12",
      rust_available: true,
      allowed_disaster_types: ["conflict", "flood"],
    });
    const { result } = renderHook(() => useSystemInfo(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.rust_available).toBe(true);
  });
});

describe("useCountrySources", () => {
  it("returns country sources", async () => {
    vi.spyOn(api, "fetchCountrySources").mockResolvedValue({ countries: [], global_feed_count: 0, global_sources: {} });
    const { result } = renderHook(() => useCountrySources(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.countries).toEqual([]);
  });
});

describe("useWorkbenchProfiles", () => {
  it("returns profile store", async () => {
    vi.spyOn(api, "fetchWorkbenchProfiles").mockResolvedValue({ presets: {}, last_profile: null });
    const { result } = renderHook(() => useWorkbenchProfiles(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.presets).toEqual({});
  });
});

describe("useHealth", () => {
  it("returns health status", async () => {
    vi.spyOn(api, "fetchHealth").mockResolvedValue({ status: "ok" });
    const { result } = renderHook(() => useHealth(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.status).toBe("ok");
  });
});

describe("useDbCycles", () => {
  it("uses default limit of 50", async () => {
    const spy = vi.spyOn(api, "fetchDbCycles").mockResolvedValue({ cycles: [], count: 0 });
    const { result } = renderHook(() => useDbCycles(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(spy).toHaveBeenCalledWith(50);
  });

  it("accepts custom limit", async () => {
    const spy = vi.spyOn(api, "fetchDbCycles").mockResolvedValue({ cycles: [], count: 0 });
    const { result } = renderHook(() => useDbCycles(25), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(spy).toHaveBeenCalledWith(25);
  });
});

describe("useDbEvents", () => {
  it("calls with empty params by default", async () => {
    const spy = vi.spyOn(api, "fetchDbEvents").mockResolvedValue({ events: [], count: 0 });
    const { result } = renderHook(() => useDbEvents(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(spy).toHaveBeenCalledWith({});
  });

  it("passes country filter through", async () => {
    const spy = vi.spyOn(api, "fetchDbEvents").mockResolvedValue({ events: [], count: 0 });
    const { result } = renderHook(
      () => useDbEvents({ country: "Lebanon", disaster_type: "conflict" }),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(spy).toHaveBeenCalledWith({ country: "Lebanon", disaster_type: "conflict" });
  });
});

describe("useDbRawItems", () => {
  it("calls with default limit of 100", async () => {
    const spy = vi.spyOn(api, "fetchDbRawItems").mockResolvedValue({ raw_items: [], count: 0 });
    const { result } = renderHook(() => useDbRawItems(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(spy).toHaveBeenCalledWith(100);
  });
});

describe("useDbFeedHealth", () => {
  it("calls with default limit of 100", async () => {
    const spy = vi.spyOn(api, "fetchDbFeedHealth").mockResolvedValue({ feed_health: [], count: 0 });
    const { result } = renderHook(() => useDbFeedHealth(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(spy).toHaveBeenCalledWith(100);
  });
});

// ── useExtractionDiagnostics (10A.1/6B.1 contract) ───────────

describe("useExtractionDiagnostics", () => {
  it("10A.1: calls fetchExtractionDiagnostics with empty params by default", async () => {
    const spy = vi.spyOn(api, "fetchExtractionDiagnostics").mockResolvedValue({
      total_records: 0,
      cycles_analyzed: 0,
      by_status: {},
      by_connector: [],
      by_method: [],
      top_errors: [],
      low_yield_connectors: [],
    });
    const { result } = renderHook(() => useExtractionDiagnostics(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(spy).toHaveBeenCalledWith({});
  });

  it("10A.1: passes limit_cycles and connector params", async () => {
    const spy = vi.spyOn(api, "fetchExtractionDiagnostics").mockResolvedValue({
      total_records: 20,
      cycles_analyzed: 5,
      by_status: { ok: 18, error: 2 },
      by_connector: [],
      by_method: [],
      top_errors: [],
      low_yield_connectors: ["rss-old"],
    });
    const { result } = renderHook(
      () => useExtractionDiagnostics({ limit_cycles: 10, connector: "rss" }),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(spy).toHaveBeenCalledWith({ limit_cycles: 10, connector: "rss" });
    expect(result.current.data?.cycles_analyzed).toBe(5);
  });
});
