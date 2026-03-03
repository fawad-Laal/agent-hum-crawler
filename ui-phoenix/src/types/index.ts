/**
 * Project Phoenix — Core TypeScript Types
 * Mirrors the existing dashboard_api.py response shapes
 */

// ── Overview API ────────────────────────────────────────────

export interface QualityMetrics {
  cycles_analyzed: number;
  events_analyzed: number;
  duplicate_rate_estimate: number;
  traceable_rate: number;
  llm_enrichment_rate: number;
  citation_coverage: number;
}

export interface HardeningStatus {
  status: "pass" | "fail" | "unknown";
  checks?: Record<string, boolean>;
}

export interface CycleTrend {
  cycle_id: string;
  events: number;
  llm_enriched: number;
  timestamp?: string;
}

export interface QualityTrend {
  label: string;
  duplicate_rate: number;
  traceable_rate: number;
  llm_rate: number;
  citation_rate: number;
}

export interface E2ESummary {
  timestamp: string;
  status: string;
  steps: Record<string, string>;
  security_status?: string;
}

export type FeatureFlags = Record<string, boolean>;

export interface CredibilityDistribution {
  high: number;
  medium: number;
  low: number;
  unknown: number;
}

export interface SourceHealthSummary {
  working: number;
  total: number;
  top_failing: SourceFailure[];
}

export interface SourceFailure {
  source_name: string;
  connector: string;
  error: string;
  stale_streak: number;
}

export interface OverviewResponse {
  quality: QualityMetrics;
  source_health: SourceHealthSummary;
  hardening: HardeningStatus;
  cycles: CycleTrend[];
  quality_trend: QualityTrend[];
  latest_e2e_summary: E2ESummary | null;
  feature_flags: FeatureFlags;
  credibility_distribution: CredibilityDistribution | null;
}

// ── Reports API ─────────────────────────────────────────────

export interface ReportListItem {
  name: string;
  size: number;
  modified: string;
}

export interface ReportDetail {
  name: string;
  markdown: string;
}

// ── Source Check API ────────────────────────────────────────

export interface SourceCheckResult {
  connector: string;
  source_name: string;
  source_url: string;
  status: string;
  fetched_count: number;
  matched_count: number;
  error: string;
  latest_published_at: string | null;
  latest_age_days: number | null;
  freshness_status: string;
  stale_streak: number;
  stale_action: string | null;
  match_reasons: {
    country_miss?: number;
    hazard_miss?: number;
    age_filtered?: number;
  };
  working: boolean;
}

export interface SourceCheckResponse {
  status: string;
  connector_count: number;
  raw_item_count: number;
  working_sources: number;
  total_sources: number;
  source_checks: SourceCheckResult[];
}

// ── Country Sources API ─────────────────────────────────────

export interface CountrySource {
  country: string;
  feed_count: number;
  sources: Record<string, string[]>;
}

export interface CountrySourcesResponse {
  countries: CountrySource[];
  global_feed_count: number;
  global_sources: Record<string, string[]>;
}

// ── System Info API ─────────────────────────────────────────

export interface SystemInfoResponse {
  python_version: string;
  rust_available: boolean;
  allowed_disaster_types: string[];
}

// ── Workbench API ───────────────────────────────────────────

export interface SectionWordUsage {
  [section: string]: {
    word_count: number;
    limit: number;
  };
}

export interface WorkbenchSide {
  markdown: string;
  section_word_usage: SectionWordUsage;
}

export interface WorkbenchResponse {
  profile: Record<string, unknown>;
  template: Record<string, unknown>;
  deterministic: WorkbenchSide;
  ai: WorkbenchSide;
}

export interface WorkbenchProfileStore {
  presets: Record<string, Record<string, unknown>>;
  last_profile: Record<string, unknown> | null;
}

// ── Situation Analysis API ──────────────────────────────────

export interface SAQualityGate {
  dimension: string;
  score: number;
  max: number;
  label: string;
}

export interface SAResponse {
  markdown: string;
  output_file: string;
  quality_gate?: SAQualityGate[];
}

// ── CLI Result (generic command response) ──────────────────

export interface CliResult {
  status: string;
  output?: string;
  error?: string;
}

// ── Form / Command Types ────────────────────────────────────

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
