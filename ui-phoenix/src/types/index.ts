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
  saQualityGateSchema,
  saResponseSchema,
  cliResultSchema,
} from "@/lib/schemas";

// ── Overview API ────────────────────────────────────────────

export type QualityMetrics = z.infer<typeof qualityMetricsSchema>;
export type HardeningStatus = z.infer<typeof hardeningStatusSchema>;
export type CycleTrend = z.infer<typeof cycleTrendSchema>;
export type QualityTrend = z.infer<typeof qualityTrendSchema>;
export type E2ESummary = z.infer<typeof e2eSummarySchema>;
export type FeatureFlags = Record<string, boolean>;
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

export type SAQualityGate = z.infer<typeof saQualityGateSchema>;
export type SAResponse = z.infer<typeof saResponseSchema>;

// ── CLI Result (generic command response) ──────────────────

export type CliResult = z.infer<typeof cliResultSchema>;

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
