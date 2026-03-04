/**
 * Project Phoenix — Zod Validation Schemas
 * Runtime validation for API responses. Mirrors types/index.ts.
 * Used by apiFetch to validate response shapes at runtime.
 */

import { z } from "zod";
// ── Async Job System ───────────────────────────────────────

/** Immediate 202 response when a long-running job is enqueued. */
export const jobQueuedSchema = z.object({
  job_id: z.string(),
  status: z.enum(["queued", "running", "done", "error"]),
});

/** Polling response for GET /api/jobs/{job_id}. */
export const jobStatusSchema = z.object({
  job_id: z.string(),
  status: z.enum(["queued", "running", "done", "error"]),
  // result is the actual payload when status === "done"
  result: z.unknown().optional(),
  error: z.string().optional(),
});
// ── Overview API ────────────────────────────────────────────

export const qualityMetricsSchema = z.object({
  cycles_analyzed: z.number().optional(),
  events_analyzed: z.number().optional(),
  duplicate_rate_estimate: z.number().optional(),
  traceable_rate: z.number().optional(),
  llm_enrichment_rate: z.number().optional(),
  citation_coverage: z.number().optional(),
  citation_coverage_rate: z.number().optional(),
}).passthrough();

export const hardeningStatusSchema = z.object({
  status: z.enum(["pass", "fail", "unknown"]),
  checks: z.record(z.string(), z.boolean()).optional(),
});

export const cycleTrendSchema = z.object({
  cycle_id: z.string().optional(),
  events: z.number().optional(),
  llm_enriched: z.number().optional(),
  timestamp: z.string().optional(),
}).passthrough();

export const qualityTrendSchema = z.object({
  // backend field names (from _quality_trend())
  duplicate_rate_estimate: z.number().optional(),
  traceable_rate: z.number().optional(),
  llm_enrichment_rate: z.number().optional(),
  citation_coverage_rate: z.number().optional(),
  events_analyzed: z.number().optional(),
  limit: z.number().optional(),
  // legacy / alternate field names kept for compat
  label: z.string().optional(),
  duplicate_rate: z.number().optional(),
  llm_rate: z.number().optional(),
  citation_rate: z.number().optional(),
}).passthrough();

export const e2eSummarySchema = z.object({
  timestamp: z.string().optional(),
  status: z.string().optional(),
  steps: z.record(z.string(), z.string()).optional(),
  security_status: z.string().optional(),
}).passthrough();

// Backend returns {tier_1: N, tier_2: N, ...} or {high: N, medium: N, ...}
export const credibilityDistributionSchema = z.record(z.string(), z.number());

export const sourceFailureSchema = z.object({
  source_name: z.string(),
  connector: z.string(),
  error: z.string(),
  stale_streak: z.number(),
});

export const sourceHealthSummarySchema = z.object({
  working: z.number().optional(),
  total: z.number().optional(),
  top_failing: z.array(sourceFailureSchema).optional(),
}).passthrough();

export const overviewResponseSchema = z.object({
  quality: qualityMetricsSchema,
  source_health: sourceHealthSummarySchema,
  hardening: hardeningStatusSchema,
  cycles: z.array(cycleTrendSchema),
  quality_trend: z.array(qualityTrendSchema),
  latest_e2e_summary: e2eSummarySchema.nullable().optional(),
  feature_flags: z.record(z.string(), z.union([z.boolean(), z.number(), z.string()])).optional(),
  credibility_distribution: credibilityDistributionSchema.nullable().optional(),
});

// ── Reports API ─────────────────────────────────────────────

export const reportListItemSchema = z.object({
  name: z.string(),
  size: z.number(),
  modified: z.union([z.number(), z.string()]),  // backend sends float mtime
});

export const reportListResponseSchema = z.object({
  reports: z.array(reportListItemSchema),
});

export const reportDetailSchema = z.object({
  name: z.string(),
  markdown: z.string(),
});

// ── Source Check API ────────────────────────────────────────

export const sourceCheckResultSchema = z.object({
  connector: z.string(),
  source_name: z.string(),
  source_url: z.string(),
  status: z.string(),
  fetched_count: z.number(),
  matched_count: z.number(),
  error: z.string(),
  latest_published_at: z.string().nullable(),
  latest_age_days: z.number().nullable(),
  freshness_status: z.string(),
  stale_streak: z.number(),
  stale_action: z.string().nullable(),
  match_reasons: z.object({
    country_miss: z.number().optional(),
    hazard_miss: z.number().optional(),
    age_filtered: z.number().optional(),
  }),
  working: z.boolean(),
});

export const sourceCheckResponseSchema = z.object({
  status: z.string(),
  connector_count: z.number().optional(),
  raw_item_count: z.number().optional(),
  working_sources: z.number().optional(),
  total_sources: z.number().optional(),
  stale_sources: z.number().optional(),
  demoted_sources: z.number().optional(),
  warnings: z.array(z.string()).optional(),
  source_checks: z.array(sourceCheckResultSchema).optional(),
  connector_metrics: z.array(z.record(z.string(), z.unknown())).optional(),
  // error response fields
  error: z.string().optional(),
  command: z.array(z.string()).optional(),
}).passthrough();

// ── Country Sources API ─────────────────────────────────────

// source feeds can be plain URL strings or {name, url} objects
const feedItemSchema = z.union([z.string(), z.object({ name: z.string(), url: z.string() }).passthrough()]);

export const countrySourceSchema = z.object({
  country: z.string(),
  feed_count: z.number(),
  sources: z.record(z.string(), z.array(feedItemSchema)),
});

export const countrySourcesResponseSchema = z.object({
  countries: z.array(countrySourceSchema),
  global_feed_count: z.number(),
  global_sources: z.record(z.string(), z.array(feedItemSchema)),
});

// ── System Info API ─────────────────────────────────────────

export const systemInfoResponseSchema = z.object({
  python_version: z.string(),
  rust_available: z.boolean(),
  allowed_disaster_types: z.array(z.string()),
});

// ── Workbench API ───────────────────────────────────────────

export const sectionWordUsageSchema = z.record(
  z.string(),
  z.object({
    word_count: z.number(),
    limit: z.number(),
  })
);

export const workbenchSideSchema = z.object({
  markdown: z.string(),
  section_word_usage: sectionWordUsageSchema,
});

export const workbenchResponseSchema = z.object({
  profile: z.record(z.string(), z.unknown()),
  template: z.record(z.string(), z.unknown()),
  deterministic: workbenchSideSchema,
  ai: workbenchSideSchema,
});

export const workbenchProfileStoreSchema = z.object({
  presets: z.record(z.string(), z.record(z.string(), z.unknown())),
  last_profile: z.record(z.string(), z.unknown()).nullable(),
});

// ── Situation Analysis API ──────────────────────────────────

// Per-dimension entry used by SA quality-gate visualizations (Phase 6)
export const saQualityGateDimensionSchema = z.object({
  dimension: z.string(),
  score: z.number(),
  max: z.number(),
  label: z.string(),
}).passthrough();

// The backend returns quality_gate as a flat summary object (not an array).
// Shape comes from sa_quality_gate.score_situation_analysis() return value.
export const saQualityGateSchema = z.object({
  overall_score: z.number().optional(),
  passed: z.boolean().optional(),
  section_completeness: z.number().optional(),
  key_figure_coverage: z.number().optional(),
  citation_accuracy: z.number().optional(),
  citation_density: z.number().optional(),
  admin_coverage: z.number().optional(),
  date_attribution: z.number().optional(),
  // details can be an array OR an object depending on backend version;
  // accept any shape to avoid ZodErrors on schema changes
  details: z.unknown().optional(),
}).passthrough();

export const saResponseSchema = z.object({
  markdown: z.string(),
  output_file: z.string().optional(),   // absent on error responses
  quality_gate: saQualityGateSchema.optional(),
  status: z.string().optional(),
}).passthrough();

// ── CLI Result ──────────────────────────────────────────────

export const cliResultSchema = z.object({
  status: z.string(),
  output: z.string().optional(),
  error: z.string().optional(),
});

// ── Health ──────────────────────────────────────────────────

export const healthResponseSchema = z.object({
  status: z.string(),
});

// ── Feature Flags ───────────────────────────────────────────

export const featureFlagUpdateResponseSchema = z.object({
  feature_flags: z.record(z.string(), z.boolean()),
});

// ── Wrapped responses ───────────────────────────────────────

export const workbenchProfileStoreResponseSchema = z.object({
  status: z.string().optional(),
  store: workbenchProfileStoreSchema,
});

// ── Database Table Schemas ───────────────────────────────────

export const dbCycleRunSchema = z.object({
  id: z.number(),
  run_at: z.string(),
  connector_count: z.number(),
  raw_item_count: z.number(),
  event_count: z.number(),
  summary: z.string().optional(),
  llm_enabled: z.union([z.boolean(), z.number()]).optional(),
  llm_enriched_count: z.number().optional(),
  llm_fallback_count: z.number().optional(),
}).passthrough();

export const dbCyclesResponseSchema = z.object({
  cycles: z.array(dbCycleRunSchema),
  count: z.number(),
  db_path: z.string().optional(),
});

export const dbEventRecordSchema = z.object({
  id: z.number(),
  cycle_id: z.number(),
  event_id: z.string(),
  status: z.string(),
  connector: z.string(),
  source_type: z.string(),
  title: z.string(),
  url: z.string(),
  country: z.string(),
  disaster_type: z.string(),
  published_at: z.string().nullable().optional(),
  severity: z.string(),
  confidence: z.string(),
  summary: z.string(),
  llm_enriched: z.union([z.boolean(), z.number()]).optional(),
  corroboration_sources: z.number().optional(),
}).passthrough();

export const dbEventsResponseSchema = z.object({
  events: z.array(dbEventRecordSchema),
  count: z.number(),
});

export const dbRawItemSchema = z.object({
  id: z.number(),
  cycle_id: z.number(),
  connector: z.string(),
  source_type: z.string(),
  title: z.string(),
  url: z.string(),
  published_at: z.string().nullable().optional(),
}).passthrough();

export const dbRawItemsResponseSchema = z.object({
  raw_items: z.array(dbRawItemSchema),
  count: z.number(),
});

export const dbFeedHealthRecordSchema = z.object({
  id: z.number(),
  cycle_id: z.number(),
  connector: z.string(),
  source_name: z.string(),
  source_url: z.string(),
  status: z.string(),
  error: z.string().optional(),
  fetched_count: z.number().optional(),
  matched_count: z.number().optional(),
}).passthrough();

export const dbFeedHealthResponseSchema = z.object({
  feed_health: z.array(dbFeedHealthRecordSchema),
  count: z.number(),
});

