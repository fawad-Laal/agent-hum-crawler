/**
 * Phase 10.1 — API Client Tests
 * Exercises lib/api.ts: apiFetch internals (via exported functions),
 * pollJob (done / error paths), and every GET + POST export.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
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

// ── Helpers ──────────────────────────────────────────────────

function makeResponse(body: unknown, ok = true, status = 200): Response {
  return {
    ok,
    status,
    json: async () => body,
    text: async () =>
      typeof body === "string" ? body : JSON.stringify(body),
  } as unknown as Response;
}

// ── Fixtures ─────────────────────────────────────────────────

const OVERVIEW = {
  quality: { cycles_analyzed: 5, events_analyzed: 42 },
  source_health: { working: 4, total: 5 },
  hardening: { status: "pass" },
  cycles: [],
  quality_trend: [],
};

const REPORT_LIST = {
  reports: [{ name: "report-20260101T000000Z.md", size: 1024, modified: 1700000000 }],
};

const REPORT_DETAIL = {
  name: "report-20260101T000000Z.md",
  markdown: "# Test Report\nContent.",
};

const SYSTEM_INFO = {
  python_version: "3.12",
  rust_available: true,
  allowed_disaster_types: ["conflict", "flood"],
};

const COUNTRY_SOURCES = {
  countries: [],
  global_feed_count: 0,
  global_sources: {},
};

const WORKBENCH_PROFILES = {
  presets: {},
  last_profile: null,
};

const WORKBENCH_RESPONSE = {
  profile: {},
  template: {},
  deterministic: { markdown: "# Det", section_word_usage: {} },
  ai: { markdown: "# AI", section_word_usage: {} },
};

const SA_RESPONSE = {
  markdown: "# Situation Analysis",
  output_file: "sa-test.md",
  status: "ok",
};

const CLI_RESULT = { status: "ok", output: "cycle done" };
const SOURCE_CHECK = { status: "ok" };
const JOB_QUEUED = { job_id: "job-123", status: "queued" };
const JOB_DONE = (result: unknown) => ({
  job_id: "job-123",
  status: "done",
  result,
});

// ── Fetch mock ────────────────────────────────────────────────

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
  // suppress DEV console noise
  vi.spyOn(console, "group").mockImplementation(() => {});
  vi.spyOn(console, "groupEnd").mockImplementation(() => {});
  vi.spyOn(console, "log").mockImplementation(() => {});
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
});

const mockFetch = () => vi.mocked(globalThis.fetch);

// ── apiFetch — error paths ────────────────────────────────────

describe("apiFetch error handling", () => {
  it("throws on non-ok HTTP response", async () => {
    mockFetch().mockResolvedValueOnce(makeResponse("Not Found", false, 404));
    await expect(fetchHealth()).rejects.toThrow("API 404");
  });

  it("throws when schema validation fails", async () => {
    // Return a body that violates healthResponseSchema (missing `status`)
    mockFetch().mockResolvedValueOnce(makeResponse({}));
    await expect(fetchHealth()).rejects.toThrow();
  });
});

// ── GET endpoints ─────────────────────────────────────────────

describe("fetchOverview", () => {
  it("returns validated overview data", async () => {
    mockFetch().mockResolvedValueOnce(makeResponse(OVERVIEW));
    const result = await fetchOverview();
    expect(result.hardening.status).toBe("pass");
    expect(result.cycles).toEqual([]);
  });
});

describe("fetchReports", () => {
  it("returns flat array of report items", async () => {
    mockFetch().mockResolvedValueOnce(makeResponse(REPORT_LIST));
    const reports = await fetchReports();
    expect(reports).toHaveLength(1);
    expect(reports[0].name).toBe("report-20260101T000000Z.md");
  });
});

describe("fetchReport", () => {
  it("returns report detail with markdown", async () => {
    mockFetch().mockResolvedValueOnce(makeResponse(REPORT_DETAIL));
    const detail = await fetchReport("report-20260101T000000Z.md");
    expect(detail.markdown).toContain("Test Report");
  });

  it("URL-encodes the report name", async () => {
    mockFetch().mockResolvedValueOnce(makeResponse(REPORT_DETAIL));
    await fetchReport("report with spaces.md");
    const url = (mockFetch().mock.calls[0] as unknown[])[0] as string;
    expect(url).toContain("report%20with%20spaces.md");
  });
});

describe("fetchSystemInfo", () => {
  it("returns system info with allowed_disaster_types", async () => {
    mockFetch().mockResolvedValueOnce(makeResponse(SYSTEM_INFO));
    const info = await fetchSystemInfo();
    expect(info.python_version).toBe("3.12");
    expect(info.allowed_disaster_types).toContain("conflict");
  });
});

describe("fetchCountrySources", () => {
  it("returns country sources shape", async () => {
    mockFetch().mockResolvedValueOnce(makeResponse(COUNTRY_SOURCES));
    const data = await fetchCountrySources();
    expect(data.countries).toEqual([]);
    expect(data.global_sources).toBeDefined();
  });
});

describe("fetchWorkbenchProfiles", () => {
  it("returns profile store with presets", async () => {
    mockFetch().mockResolvedValueOnce(makeResponse(WORKBENCH_PROFILES));
    const store = await fetchWorkbenchProfiles();
    expect(store.presets).toEqual({});
    expect(store.last_profile).toBeNull();
  });
});

describe("fetchHealth", () => {
  it("returns status string", async () => {
    mockFetch().mockResolvedValueOnce(makeResponse({ status: "ok" }));
    const health = await fetchHealth();
    expect(health.status).toBe("ok");
  });
});

const DB_CYCLES_RESP = { cycles: [], count: 0 };
const DB_EVENTS_RESP = { events: [], count: 0 };
const DB_RAW_RESP = { raw_items: [], count: 0 };
const DB_FEED_RESP = { feed_health: [], count: 0 };
const EXTRACTION_RESP = {
  total_records: 0,
  cycles_analyzed: 0,
  by_status: {},
  by_connector: [],
  by_method: [],
  top_errors: [],
  low_yield_connectors: [],
};

describe("fetchDbCycles", () => {
  it("calls /db/cycles with limit query param", async () => {
    mockFetch().mockResolvedValueOnce(makeResponse(DB_CYCLES_RESP));
    await fetchDbCycles(25);
    const url = (mockFetch().mock.calls[0] as unknown[])[0] as string;
    expect(url).toContain("limit=25");
  });

  it("uses default limit=50", async () => {
    mockFetch().mockResolvedValueOnce(makeResponse(DB_CYCLES_RESP));
    await fetchDbCycles();
    const url = (mockFetch().mock.calls[0] as unknown[])[0] as string;
    expect(url).toContain("limit=50");
  });
});

describe("fetchDbEvents", () => {
  it("calls /db/events with no params when empty", async () => {
    mockFetch().mockResolvedValueOnce(makeResponse(DB_EVENTS_RESP));
    await fetchDbEvents();
    const url = (mockFetch().mock.calls[0] as unknown[])[0] as string;
    expect(url).toBe("/api/db/events");
  });

  it("appends country and disaster_type query params", async () => {
    mockFetch().mockResolvedValueOnce(makeResponse(DB_EVENTS_RESP));
    await fetchDbEvents({ limit: 50, country: "Lebanon", disaster_type: "conflict" });
    const url = (mockFetch().mock.calls[0] as unknown[])[0] as string;
    expect(url).toContain("country=Lebanon");
    expect(url).toContain("disaster_type=conflict");
    expect(url).toContain("limit=50");
  });
});

describe("fetchDbRawItems", () => {
  it("calls /db/raw-items with limit", async () => {
    mockFetch().mockResolvedValueOnce(makeResponse(DB_RAW_RESP));
    await fetchDbRawItems(75);
    const url = (mockFetch().mock.calls[0] as unknown[])[0] as string;
    expect(url).toContain("limit=75");
  });
});

describe("fetchDbFeedHealth", () => {
  it("calls /db/feed-health with limit", async () => {
    mockFetch().mockResolvedValueOnce(makeResponse(DB_FEED_RESP));
    await fetchDbFeedHealth(20);
    const url = (mockFetch().mock.calls[0] as unknown[])[0] as string;
    expect(url).toContain("limit=20");
  });
});

describe("fetchExtractionDiagnostics", () => {
  it("calls base endpoint when no params", async () => {
    mockFetch().mockResolvedValueOnce(makeResponse(EXTRACTION_RESP));
    await fetchExtractionDiagnostics();
    const url = (mockFetch().mock.calls[0] as unknown[])[0] as string;
    expect(url).toBe("/api/db/extraction-diagnostics");
  });

  it("appends limit_cycles and connector params", async () => {
    mockFetch().mockResolvedValueOnce(makeResponse(EXTRACTION_RESP));
    await fetchExtractionDiagnostics({ limit_cycles: 5, connector: "rss" });
    const url = (mockFetch().mock.calls[0] as unknown[])[0] as string;
    expect(url).toContain("limit_cycles=5");
    expect(url).toContain("connector=rss");
  });
});

// ── POST endpoints (202 + pollJob pattern) ────────────────────

describe("runCycle", () => {
  it("POSTs params and resolves with CLI result when job succeeds", async () => {
    mockFetch()
      .mockResolvedValueOnce(makeResponse(JOB_QUEUED, true, 202))  // POST
      .mockResolvedValueOnce(makeResponse(JOB_DONE(CLI_RESULT)));   // poll
    const result = await runCycle({ countries: "Lebanon", disaster_types: "conflict", limit: 10, max_age_days: 30 });
    expect(result.status).toBe("ok");
    expect(mockFetch()).toHaveBeenCalledTimes(2);
  });

  it("throws when the polled job errors", async () => {
    mockFetch()
      .mockResolvedValueOnce(makeResponse(JOB_QUEUED, true, 202))
      .mockResolvedValueOnce(makeResponse({ job_id: "job-123", status: "error", error: "cycle crashed" }));
    await expect(runCycle({ countries: "Lebanon", disaster_types: "conflict", limit: 10, max_age_days: 30 }))
      .rejects.toThrow("cycle crashed");
  });
});

describe("writeReport", () => {
  it("resolves with CLI result on success", async () => {
    mockFetch()
      .mockResolvedValueOnce(makeResponse(JOB_QUEUED, true, 202))
      .mockResolvedValueOnce(makeResponse(JOB_DONE(CLI_RESULT)));
    const result = await writeReport({
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
    });
    expect(result.status).toBe("ok");
  });
});

describe("runSourceCheck", () => {
  it("resolves with source check response", async () => {
    mockFetch()
      .mockResolvedValueOnce(makeResponse(JOB_QUEUED, true, 202))
      .mockResolvedValueOnce(makeResponse(JOB_DONE(SOURCE_CHECK)));
    const result = await runSourceCheck({ countries: "Lebanon", disaster_types: "conflict", limit: 10, max_age_days: 30 });
    expect(result.status).toBe("ok");
  });
});

describe("writeSA", () => {
  it("resolves with SA markdown on success", async () => {
    mockFetch()
      .mockResolvedValueOnce(makeResponse(JOB_QUEUED, true, 202))
      .mockResolvedValueOnce(makeResponse(JOB_DONE(SA_RESPONSE)));
    const result = await writeSA({
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
    });
    expect(result.markdown).toContain("Situation Analysis");
  });
});

describe("runWorkbench", () => {
  it("resolves with workbench comparison", async () => {
    mockFetch()
      .mockResolvedValueOnce(makeResponse(JOB_QUEUED, true, 202))
      .mockResolvedValueOnce(makeResponse(JOB_DONE(WORKBENCH_RESPONSE)));
    const result = await runWorkbench({ template: "default" });
    expect(result.deterministic.markdown).toBeDefined();
  });
});

describe("saveWorkbenchProfile", () => {
  it("POSTs save request and returns updated store", async () => {
    const store = { presets: { "my-profile": {} }, last_profile: null };
    mockFetch().mockResolvedValueOnce(makeResponse({ status: "ok", store }));
    const result = await saveWorkbenchProfile("my-profile", { template: "default" });
    expect(result.presets).toHaveProperty("my-profile");
  });
});

describe("deleteWorkbenchProfile", () => {
  it("POSTs delete request and returns updated store", async () => {
    const store = { presets: {}, last_profile: null };
    mockFetch().mockResolvedValueOnce(makeResponse({ status: "ok", store }));
    const result = await deleteWorkbenchProfile("my-profile");
    expect(result.presets).toEqual({});
  });
});

describe("runPipeline", () => {
  it("resolves with CLI result when pipeline completes", async () => {
    mockFetch()
      .mockResolvedValueOnce(makeResponse(JOB_QUEUED, true, 202))
      .mockResolvedValueOnce(makeResponse(JOB_DONE(CLI_RESULT)));
    const result = await runPipeline({
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
    });
    expect(result.status).toBe("ok");
  });
});

describe("rerunLastWorkbench", () => {
  it("POSTs rerun-last and returns workbench response", async () => {
    mockFetch()
      .mockResolvedValueOnce(makeResponse(JOB_QUEUED, true, 202))
      .mockResolvedValueOnce(makeResponse(JOB_DONE(WORKBENCH_RESPONSE)));
    const result = await rerunLastWorkbench();
    expect(result.ai.markdown).toBeDefined();
  });
});

describe("updateFeatureFlag", () => {
  it("POSTs flag update and returns updated flags map", async () => {
    const flagsMap = { use_llm: true, strict_filter: false };
    mockFetch().mockResolvedValueOnce(makeResponse({ feature_flags: flagsMap }));
    const result = await updateFeatureFlag("use_llm", true);
    expect(result.feature_flags.use_llm).toBe(true);
  });
});

// ── pollJob — running → done back-off path ────────────────────

describe("pollJob back-off (running → done)", () => {
  it("retries until job is done", async () => {
    vi.useFakeTimers();
    const runningJob = { job_id: "job-123", status: "running" };

    mockFetch()
      .mockResolvedValueOnce(makeResponse(JOB_QUEUED, true, 202)) // POST runCycle
      .mockResolvedValueOnce(makeResponse(runningJob))             // poll 1: running
      .mockResolvedValueOnce(makeResponse(JOB_DONE(CLI_RESULT)));  // poll 2: done

    const promise = runCycle({ countries: "Lebanon", disaster_types: "conflict", limit: 10, max_age_days: 30 });

    // Advance timers past the 1 s back-off sleep
    await vi.runAllTimersAsync();

    const result = await promise;
    expect(result.status).toBe("ok");
    expect(mockFetch()).toHaveBeenCalledTimes(3);

    vi.useRealTimers();
  });
});
