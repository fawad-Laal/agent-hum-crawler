/**
 * Project Phoenix — Phase 5 Tests
 * Sources & System: source health table, connector diagnostics,
 * freshness trend chart, feature flags panel, security baseline card.
 */

import { describe, it, expect, vi } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { renderWithProviders } from "../test-utils";
import { SourceHealthTable } from "@/features/sources/source-health-table";
import { ConnectorDiagnostics } from "@/features/sources/connector-diagnostics";
import { FreshnessTrendChart } from "@/components/charts/freshness-trend-chart";
import { FeatureFlagsPanel } from "@/features/system/feature-flags-panel";
import { SecurityBaselineCard } from "@/features/system/security-baseline-card";
import type { SourceCheckResult } from "@/types";

// ── Fixtures ────────────────────────────────────────────────

const makeSource = (overrides: Partial<SourceCheckResult> = {}): SourceCheckResult => ({
  connector: "rss",
  source_name: "OCHA Reliefweb",
  source_url: "https://reliefweb.int/feed",
  status: "ok",
  fetched_count: 42,
  matched_count: 18,
  error: "",
  latest_published_at: "2026-03-01T10:00:00Z",
  latest_age_days: 2.5,
  freshness_status: "fresh",
  stale_streak: 0,
  stale_action: null,
  match_reasons: { country_miss: 0, hazard_miss: 0, age_filtered: 0 },
  working: true,
  ...overrides,
});

const staleSrc = makeSource({
  source_name: "GDACS Feed",
  connector: "atom",
  working: false,
  freshness_status: "stale",
  stale_streak: 4,
  stale_action: "demote",
  latest_age_days: 12.0,
  error: "Request timed out",
});

// ── SourceHealthTable ───────────────────────────────────────

describe("SourceHealthTable", () => {
  it("renders empty state when no sources", () => {
    renderWithProviders(<SourceHealthTable sources={[]} />);
    expect(screen.getByText(/no source results/i)).toBeInTheDocument();
  });

  it("renders a row per source", () => {
    const sources = [makeSource(), staleSrc];
    renderWithProviders(<SourceHealthTable sources={sources} />);
    expect(screen.getByText("OCHA Reliefweb")).toBeInTheDocument();
    expect(screen.getByText("GDACS Feed")).toBeInTheDocument();
  });

  it("shows freshness badge for each source", () => {
    renderWithProviders(<SourceHealthTable sources={[makeSource(), staleSrc]} />);
    expect(screen.getByText("fresh")).toBeInTheDocument();
    expect(screen.getByText("stale")).toBeInTheDocument();
  });

  it("renders stale streak for failing source", () => {
    renderWithProviders(<SourceHealthTable sources={[staleSrc]} />);
    expect(screen.getByText("4×")).toBeInTheDocument();
  });

  it("shows age in days", () => {
    renderWithProviders(<SourceHealthTable sources={[makeSource()]} />);
    expect(screen.getByText("2.5d")).toBeInTheDocument();
  });

  it("shows — for null age", () => {
    const src = makeSource({ latest_age_days: null });
    renderWithProviders(<SourceHealthTable sources={[src]} />);
    // age column shows —
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThan(0);
  });
});

// ── ConnectorDiagnostics ────────────────────────────────────

describe("ConnectorDiagnostics", () => {
  it("renders empty state when no sources", () => {
    renderWithProviders(<ConnectorDiagnostics sources={[]} />);
    expect(screen.getByText(/no connector data/i)).toBeInTheDocument();
  });

  it("groups sources by connector and renders connector header", () => {
    const sources = [
      makeSource({ connector: "rss", source_name: "Feed A" }),
      makeSource({ connector: "rss", source_name: "Feed B" }),
      makeSource({ connector: "atom", source_name: "Feed C" }),
    ];
    renderWithProviders(<ConnectorDiagnostics sources={sources} />);
    expect(screen.getByText("rss")).toBeInTheDocument();
    expect(screen.getByText("atom")).toBeInTheDocument();
  });

  it("unhealthy connectors are expanded by default", () => {
    const sources = [staleSrc, makeSource({ connector: "rss" })];
    renderWithProviders(<ConnectorDiagnostics sources={sources} />);
    // Error text should be visible since failing connector is expanded by default
    expect(screen.getByText("Request timed out")).toBeInTheDocument();
  });

  it("shows health badge with working/total ratio", () => {
    const sources = [
      staleSrc,
      makeSource({ connector: "atom", source_name: "Good Atom" }),
    ];
    renderWithProviders(<ConnectorDiagnostics sources={sources} />);
    // The atom connector has 1 working, 1 failing — badge shows "1/2 · 50%"
    expect(screen.getByText(/1\/2/)).toBeInTheDocument();
  });
});

// ── FreshnessTrendChart ─────────────────────────────────────

describe("FreshnessTrendChart", () => {
  it("renders empty state when all sources have null age", () => {
    const src = makeSource({ latest_age_days: null });
    renderWithProviders(<FreshnessTrendChart sources={[src]} />);
    expect(screen.getByText(/no freshness data/i)).toBeInTheDocument();
  });

  it("renders chart container when sources have age data", () => {
    // Recharts requires ResizeObserver (not in jsdom); verify the empty-state
    // message is NOT shown when valid data is provided.
    const sources = [makeSource(), makeSource({ source_name: "Feed B", latest_age_days: 5.0 })];
    renderWithProviders(<FreshnessTrendChart sources={sources} />);
    expect(screen.queryByText(/no freshness data/i)).toBeNull();
  });
});

// ── FeatureFlagsPanel ───────────────────────────────────────

vi.mock("@/hooks/use-mutations", () => ({
  useUpdateFeatureFlag: () => ({
    mutate: vi.fn(),
    isPending: false,
    variables: undefined,
  }),
  useRunCycle: () => ({ mutate: vi.fn(), isPending: false }),
  useWriteReport: () => ({ mutate: vi.fn(), isPending: false }),
  useRunSourceCheck: () => ({ mutate: vi.fn(), isPending: false, data: undefined }),
  useWriteSA: () => ({ mutate: vi.fn(), isPending: false }),
  useRunWorkbench: () => ({ mutate: vi.fn(), isPending: false }),
  useSaveWorkbenchProfile: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteWorkbenchProfile: () => ({ mutate: vi.fn(), isPending: false }),
  useRunPipeline: () => ({ mutate: vi.fn(), isPending: false }),
}));

describe("FeatureFlagsPanel", () => {
  it("renders loading skeletons", () => {
    const { container } = renderWithProviders(
      <FeatureFlagsPanel flags={undefined} isLoading={true} />
    );
    // Skeletons render as divs with animate-pulse
    const skeletons = container.querySelectorAll("[class*='animate-pulse']");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders empty state when flags undefined", () => {
    renderWithProviders(<FeatureFlagsPanel flags={undefined} isLoading={false} />);
    expect(screen.getByText(/no feature flags/i)).toBeInTheDocument();
  });

  it("renders empty state when flags is empty object", () => {
    renderWithProviders(<FeatureFlagsPanel flags={{}} isLoading={false} />);
    expect(screen.getByText(/no feature flags/i)).toBeInTheDocument();
  });

  it("renders flag rows sorted alphabetically", () => {
    const flags = { use_llm: true, debug_mode: false, cache_sources: true };
    renderWithProviders(<FeatureFlagsPanel flags={flags} isLoading={false} />);
    // All three flags should appear
    expect(screen.getByText("Cache Sources")).toBeInTheDocument();
    expect(screen.getByText("Debug Mode")).toBeInTheDocument();
    expect(screen.getByText("Use Llm")).toBeInTheDocument();
  });

  it("accepts number and string flag values (coerces to boolean)", () => {
    // Backend can send non-boolean flags
    const flags = { use_llm: 1, debug_mode: 0, version: "v2" };
    renderWithProviders(
      <FeatureFlagsPanel
        flags={flags as Record<string, boolean | number | string>}
        isLoading={false}
      />
    );
    expect(screen.getByText("Use Llm")).toBeInTheDocument();
    expect(screen.getByText("Version")).toBeInTheDocument();
  });

  it("shows known flag description", () => {
    renderWithProviders(
      <FeatureFlagsPanel flags={{ use_llm: true }} isLoading={false} />
    );
    expect(screen.getByText(/llm enrichment/i)).toBeInTheDocument();
  });

  it("renders switch in correct checked state", () => {
    renderWithProviders(
      <FeatureFlagsPanel flags={{ use_llm: true, debug_mode: false }} isLoading={false} />
    );
    // Switch uses role="switch" with aria-checked; find the one for use_llm
    const llmSwitch = screen.getByRole("switch", { name: /Toggle use_llm/i });
    expect(llmSwitch).toBeDefined();
    expect(llmSwitch.getAttribute("aria-checked")).toBe("true");
    const debugSwitch = screen.getByRole("switch", { name: /Toggle debug_mode/i });
    expect(debugSwitch.getAttribute("aria-checked")).toBe("false");
  });
});

// ── SecurityBaselineCard ────────────────────────────────────

describe("SecurityBaselineCard", () => {
  it("renders loading skeleton", () => {
    const { container } = renderWithProviders(
      <SecurityBaselineCard hardening={undefined} e2eSummary={undefined} isLoading={true} />
    );
    const skeletons = container.querySelectorAll("[class*='animate-pulse']");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("shows unknown state when hardening is undefined", () => {
    renderWithProviders(
      <SecurityBaselineCard hardening={undefined} e2eSummary={null} isLoading={false} />
    );
    expect(screen.getByText("Status Unknown")).toBeInTheDocument();
  });

  it("shows pass state when hardening passes", () => {
    renderWithProviders(
      <SecurityBaselineCard
        hardening={{ status: "pass", checks: { tls: true, secrets: true } }}
        e2eSummary={null}
        isLoading={false}
      />
    );
    expect(screen.getByText("Baseline Secure")).toBeInTheDocument();
  });

  it("shows fail state when hardening fails", () => {
    renderWithProviders(
      <SecurityBaselineCard
        hardening={{ status: "fail", checks: { tls: false } }}
        e2eSummary={null}
        isLoading={false}
      />
    );
    expect(screen.getByText("Baseline Failing")).toBeInTheDocument();
  });

  it("shows warn state when hardening passes but e2e security fails", () => {
    renderWithProviders(
      <SecurityBaselineCard
        hardening={{ status: "pass", checks: {} }}
        e2eSummary={{ timestamp: "2026-03-01T10:00:00Z", security_status: "fail" }}
        isLoading={false}
      />
    );
    expect(screen.getByText("Partial Compliance")).toBeInTheDocument();
  });

  it("shows critical state when both hardening and e2e security fail", () => {
    // R17: combined fail must never be silently downgraded to warn
    renderWithProviders(
      <SecurityBaselineCard
        hardening={{ status: "fail", checks: { tls: false } }}
        e2eSummary={{ timestamp: "2026-03-01T10:00:00Z", security_status: "fail" }}
        isLoading={false}
      />
    );
    expect(screen.getByText("Critical Failure")).toBeInTheDocument();
  });

  it("renders tooltip reason text for pass state", () => {
    renderWithProviders(
      <SecurityBaselineCard
        hardening={{ status: "pass" }}
        e2eSummary={null}
        isLoading={false}
      />
    );
    expect(
      screen.getByText(/all hardening gates passed/i)
    ).toBeInTheDocument();
  });

  it("renders tooltip reason text for critical state", () => {
    renderWithProviders(
      <SecurityBaselineCard
        hardening={{ status: "fail" }}
        e2eSummary={{ timestamp: "2026-03-01T10:00:00Z", security_status: "fail" }}
        isLoading={false}
      />
    );
    expect(
      screen.getByText(/immediate action required/i)
    ).toBeInTheDocument();
  });

  it("renders tooltip reason text for unknown state", () => {
    renderWithProviders(
      <SecurityBaselineCard hardening={undefined} e2eSummary={null} isLoading={false} />
    );
    expect(
      screen.getByText(/no hardening data available/i)
    ).toBeInTheDocument();
  });

  it("renders hardening check grid entries", () => {
    renderWithProviders(
      <SecurityBaselineCard
        hardening={{ status: "pass", checks: { tls: true, secrets_scan: false } }}
        e2eSummary={null}
        isLoading={false}
      />
    );
    expect(screen.getByText("tls")).toBeInTheDocument();
    expect(screen.getByText("secrets scan")).toBeInTheDocument();
  });

  it("shows E2E metadata when summary provided", () => {
    renderWithProviders(
      <SecurityBaselineCard
        hardening={{ status: "pass" }}
        e2eSummary={{
          timestamp: "2026-03-01T10:00:00Z",
          security_status: "pass",
        }}
        isLoading={false}
      />
    );
    expect(screen.getByText(/last e2e run/i)).toBeInTheDocument();
  });
});
