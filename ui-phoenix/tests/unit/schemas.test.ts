/**
 * Phase 2 — Zod Schema Tests
 * Validates that Zod schemas correctly parse valid data
 * and reject invalid data at runtime.
 */

import { describe, it, expect } from "vitest";
import {
  overviewResponseSchema,
  reportListResponseSchema,
  reportDetailSchema,
  countrySourcesResponseSchema,
  systemInfoResponseSchema,
  healthResponseSchema,
  cliResultSchema,
  credibilityDistributionSchema,
  sourceCheckResponseSchema,
  workbenchResponseSchema,
  workbenchProfileStoreSchema,
  saResponseSchema,
  sectionWordUsageSchema,
} from "@/lib/schemas";

// ── Fixtures ────────────────────────────────────────────────

const validOverview = {
  quality: {
    cycles_analyzed: 5,
    events_analyzed: 120,
    duplicate_rate_estimate: 0.08,
    traceable_rate: 0.92,
    llm_enrichment_rate: 0.75,
    citation_coverage: 0.88,
  },
  source_health: {
    working: 12,
    total: 15,
    top_failing: [
      { source_name: "reliefweb", connector: "rss", error: "timeout", stale_streak: 3 },
    ],
  },
  hardening: { status: "pass" as const, checks: { a: true } },
  cycles: [{ cycle_id: "c1", events: 25, llm_enriched: 18 }],
  quality_trend: [
    { label: "q1", duplicate_rate: 0.1, traceable_rate: 0.9, llm_rate: 0.8, citation_rate: 0.7 },
  ],
  latest_e2e_summary: null,
  feature_flags: { use_llm: true, hardened_mode: false },
  credibility_distribution: { high: 10, medium: 5, low: 2, unknown: 1 },
};

// ── Tests ───────────────────────────────────────────────────

describe("overviewResponseSchema", () => {
  it("parses valid overview data", () => {
    const result = overviewResponseSchema.parse(validOverview);
    expect(result.quality.cycles_analyzed).toBe(5);
    expect(result.hardening.status).toBe("pass");
  });

  it("rejects missing quality field", () => {
    const bad = { ...validOverview, quality: undefined };
    expect(() => overviewResponseSchema.parse(bad)).toThrow();
  });

  it("rejects invalid hardening status", () => {
    const bad = {
      ...validOverview,
      hardening: { status: "maybe" },
    };
    expect(() => overviewResponseSchema.parse(bad)).toThrow();
  });
});

describe("reportListResponseSchema", () => {
  it("parses valid report list", () => {
    const result = reportListResponseSchema.parse({
      reports: [
        { name: "report-1.md", size: 1024, modified: "2025-01-01T00:00:00Z" },
      ],
    });
    expect(result.reports).toHaveLength(1);
  });

  it("rejects missing reports array", () => {
    expect(() => reportListResponseSchema.parse({})).toThrow();
  });
});

describe("reportDetailSchema", () => {
  it("parses valid report detail", () => {
    const result = reportDetailSchema.parse({ name: "r1.md", markdown: "# Hello" });
    expect(result.markdown).toBe("# Hello");
  });
});

describe("countrySourcesResponseSchema", () => {
  it("parses valid country sources with Record types", () => {
    const data = {
      countries: [
        {
          country: "Ethiopia",
          feed_count: 12,
          sources: { government: ["src1"], un: ["src2"] },
        },
      ],
      global_feed_count: 5,
      global_sources: { ngo: ["src3"] },
    };
    const result = countrySourcesResponseSchema.parse(data);
    expect(result.countries[0].sources).toHaveProperty("government");
    expect(result.global_sources).toHaveProperty("ngo");
  });
});

describe("systemInfoResponseSchema", () => {
  it("parses valid system info", () => {
    const result = systemInfoResponseSchema.parse({
      python_version: "3.12.0",
      rust_available: true,
      allowed_disaster_types: ["flood", "cyclone"],
    });
    expect(result.rust_available).toBe(true);
  });
});

describe("healthResponseSchema", () => {
  it("parses valid health", () => {
    const result = healthResponseSchema.parse({ status: "ok" });
    expect(result.status).toBe("ok");
  });
});

describe("cliResultSchema", () => {
  it("parses success result", () => {
    const result = cliResultSchema.parse({ status: "ok", output: "done" });
    expect(result.status).toBe("ok");
  });

  it("parses error result", () => {
    const result = cliResultSchema.parse({ status: "error", error: "failed" });
    expect(result.error).toBe("failed");
  });
});

describe("credibilityDistributionSchema", () => {
  it("parses valid distribution", () => {
    const result = credibilityDistributionSchema.parse({
      high: 10,
      medium: 5,
      low: 2,
      unknown: 1,
    });
    expect(result.high + result.medium + result.low + result.unknown).toBe(18);
  });

  it("rejects missing tier", () => {
    expect(() =>
      credibilityDistributionSchema.parse({ high: 10, medium: 5 })
    ).toThrow();
  });
});

// ── Source Check Response ───────────────────────────────────

describe("sourceCheckResponseSchema", () => {
  it("parses valid source check response", () => {
    const data = {
      status: "completed",
      connector_count: 3,
      raw_item_count: 42,
      working_sources: 10,
      total_sources: 12,
      source_checks: [
        {
          connector: "rss",
          source_name: "reliefweb",
          source_url: "https://reliefweb.int/feed",
          status: "working",
          fetched_count: 20,
          matched_count: 15,
          error: "",
          latest_published_at: "2026-01-01T00:00:00Z",
          latest_age_days: 2,
          freshness_status: "fresh",
          stale_streak: 0,
          stale_action: null,
          match_reasons: { country_miss: 3, hazard_miss: 2 },
          working: true,
        },
      ],
    };
    const result = sourceCheckResponseSchema.parse(data);
    expect(result.source_checks).toHaveLength(1);
    expect(result.source_checks[0].working).toBe(true);
  });

  it("rejects missing working_sources field", () => {
    expect(() =>
      sourceCheckResponseSchema.parse({
        status: "done",
        connector_count: 1,
        raw_item_count: 5,
        total_sources: 3,
        source_checks: [],
      })
    ).toThrow();
  });
});

// ── Workbench Response ──────────────────────────────────────

describe("workbenchResponseSchema", () => {
  it("parses valid workbench response", () => {
    const data = {
      profile: { country: "Ethiopia" },
      template: { title: "Brief" },
      deterministic: {
        markdown: "# Report",
        section_word_usage: {
          overview: { word_count: 120, limit: 200 },
        },
      },
      ai: {
        markdown: "# AI Report",
        section_word_usage: {},
      },
    };
    const result = workbenchResponseSchema.parse(data);
    expect(result.deterministic.markdown).toBe("# Report");
    expect(result.ai.section_word_usage).toEqual({});
  });
});

// ── Workbench Profile Store ─────────────────────────────────

describe("workbenchProfileStoreSchema", () => {
  it("parses valid profile store with presets", () => {
    const data = {
      presets: {
        brief: { country: "Ethiopia", use_llm: false },
        detailed: { country: "Madagascar", use_llm: true },
      },
      last_profile: { country: "Ethiopia" },
    };
    const result = workbenchProfileStoreSchema.parse(data);
    expect(Object.keys(result.presets)).toHaveLength(2);
    expect(result.last_profile).not.toBeNull();
  });

  it("accepts null last_profile", () => {
    const data = { presets: {}, last_profile: null };
    const result = workbenchProfileStoreSchema.parse(data);
    expect(result.last_profile).toBeNull();
  });
});

// ── SA Response ─────────────────────────────────────────────

describe("saResponseSchema", () => {
  it("parses valid SA response without quality gate", () => {
    const result = saResponseSchema.parse({
      markdown: "# Situation Analysis",
      output_file: "sa-report.md",
    });
    expect(result.output_file).toBe("sa-report.md");
    expect(result.quality_gate).toBeUndefined();
  });

  it("parses SA response with quality gate", () => {
    const result = saResponseSchema.parse({
      markdown: "# SA",
      output_file: "sa.md",
      quality_gate: [
        { dimension: "accuracy", score: 8, max: 10, label: "Good" },
      ],
    });
    expect(result.quality_gate).toHaveLength(1);
    expect(result.quality_gate![0].score).toBe(8);
  });
});

// ── Section Word Usage ──────────────────────────────────────

describe("sectionWordUsageSchema", () => {
  it("parses valid section word usage", () => {
    const data = {
      overview: { word_count: 150, limit: 200 },
      details: { word_count: 500, limit: 600 },
    };
    const result = sectionWordUsageSchema.parse(data);
    expect(result["overview"].word_count).toBe(150);
    expect(result["details"].limit).toBe(600);
  });

  it("accepts empty record", () => {
    const result = sectionWordUsageSchema.parse({});
    expect(Object.keys(result)).toHaveLength(0);
  });
});
