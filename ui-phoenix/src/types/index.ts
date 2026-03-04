/**
 * Project Phoenix — Core TypeScript Types
 * Derived from Zod schemas via z.infer — single source of truth.
 * Import types here; define shapes in lib/schemas.ts.
 */

import type { z } from "zod";
import type {
  qualityMetricsSchema,
  hardeningStatusSchema,
  cycleTrendSchema,
  qualityTrendSchema,
  e2eSummarySchema,
  credibilityDistributionSchema,
  sourceFailureSchema,
  sourceHealthSummarySchema,
  overviewResponseSchema,
  reportListItemSchema,
  reportDetailSchema,
  sourceCheckResultSchema,
  sourceCheckResponseSchema,
  countrySourceSchema,
  countrySourcesResponseSchema,
  systemInfoResponseSchema,
  sectionWordUsageSchema,
  workbenchSideSchema,
  workbenchResponseSchema,
  workbenchProfileStoreSchema,
  saQualityGateDimensionSchema,
  saQualityGateSchema,
  saResponseSchema,
  cliResultSchema,
  dbCycleRunSchema,
  dbCyclesResponseSchema,
  dbEventRecordSchema,
  dbEventsResponseSchema,
  dbRawItemSchema,
  dbRawItemsResponseSchema,
  dbFeedHealthRecordSchema,
  dbFeedHealthResponseSchema,
  jobQueuedSchema,
  jobStatusSchema,
} from "@/lib/schemas";

// ── Overview API ────────────────────────────────────────────

export type QualityMetrics = z.infer<typeof qualityMetricsSchema>;
export type HardeningStatus = z.infer<typeof hardeningStatusSchema>;
export type CycleTrend = z.infer<typeof cycleTrendSchema>;
export type QualityTrend = z.infer<typeof qualityTrendSchema>;
export type E2ESummary = z.infer<typeof e2eSummarySchema>;
export type FeatureFlags = Record<string, boolean | number | string>;
export type CredibilityDistribution = z.infer<typeof credibilityDistributionSchema>;
export type SourceFailure = z.infer<typeof sourceFailureSchema>;
export type SourceHealthSummary = z.infer<typeof sourceHealthSummarySchema>;
export type OverviewResponse = z.infer<typeof overviewResponseSchema>;

// ── Reports API ─────────────────────────────────────────────

export type ReportListItem = z.infer<typeof reportListItemSchema>;
export type ReportDetail = z.infer<typeof reportDetailSchema>;

// ── Source Check API ────────────────────────────────────────

export type SourceCheckResult = z.infer<typeof sourceCheckResultSchema>;
export type SourceCheckResponse = z.infer<typeof sourceCheckResponseSchema>;

// ── Country Sources API ─────────────────────────────────────

export type CountrySource = z.infer<typeof countrySourceSchema>;
export type CountrySourcesResponse = z.infer<typeof countrySourcesResponseSchema>;

// ── System Info API ─────────────────────────────────────────

export type SystemInfoResponse = z.infer<typeof systemInfoResponseSchema>;

// ── Workbench API ───────────────────────────────────────────

export type SectionWordUsage = z.infer<typeof sectionWordUsageSchema>;
export type WorkbenchSide = z.infer<typeof workbenchSideSchema>;
export type WorkbenchResponse = z.infer<typeof workbenchResponseSchema>;
export type WorkbenchProfileStore = z.infer<typeof workbenchProfileStoreSchema>;

// ── Situation Analysis API ──────────────────────────────────
/** Per-dimension entry for Phase 6 SA quality-gate visualization. */
export type SAQualityGateDimension = z.infer<typeof saQualityGateDimensionSchema>;
/** Flat summary object returned by the backend quality gate scorer. */export type SAQualityGate = z.infer<typeof saQualityGateSchema>;
export type SAResponse = z.infer<typeof saResponseSchema>;

// ── CLI Result (generic command response) ──────────────────

export type CliResult = z.infer<typeof cliResultSchema>;

// ── Database table types ─────────────────────────────────────

export type DbCycleRun = z.infer<typeof dbCycleRunSchema>;
export type DbCyclesResponse = z.infer<typeof dbCyclesResponseSchema>;
export type DbEventRecord = z.infer<typeof dbEventRecordSchema>;
export type DbEventsResponse = z.infer<typeof dbEventsResponseSchema>;
export type DbRawItem = z.infer<typeof dbRawItemSchema>;
export type DbRawItemsResponse = z.infer<typeof dbRawItemsResponseSchema>;
export type DbFeedHealthRecord = z.infer<typeof dbFeedHealthRecordSchema>;
export type DbFeedHealthResponse = z.infer<typeof dbFeedHealthResponseSchema>;

// ── Async Job System ──────────────────────────────────────────

/** 202 response when a job is enqueued. */
export type JobQueued = z.infer<typeof jobQueuedSchema>;
/** Polling response from GET /api/jobs/{job_id}. */
export type JobStatus = z.infer<typeof jobStatusSchema>;

// ── Form / Command Types (not API responses — kept manual) ──

export interface CollectionForm {
  countries: string;
  disaster_types: string;
  max_age_days: number;
  limit: number;
  limit_cycles: number;
  limit_events: number;
  country_min_events: number;
  max_per_connector: number;
  max_per_source: number;
  report_template: string;
  use_llm: boolean;
  // Situation Analysis
  sa_title: string;
  sa_event_name: string;
  sa_event_type: string;
  sa_period: string;
  sa_template: string;
  sa_limit_events: number;
  sa_quality_gate: boolean;
  // Pipeline
  pipeline_report_title: string;
  pipeline_sa_title: string;
  pipeline_event_name: string;
  pipeline_event_type: string;
  pipeline_period: string;
}
