/**
 * Project Phoenix — Phase 6 Tests
 * Situation Analysis: SAQualityGateChart, SAPage form, output panel, exports.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../test-utils";
import { SAQualityGateChart } from "@/components/charts/sa-quality-gate-chart";
import { SAPage } from "@/features/situation-analysis/sa-page";
import type { SAQualityGate, SAResponse } from "@/types";

// ── Module mock (hoisted by vitest) ──────────────────────────
// Must be at top level; we set a sensible default per describe block.

vi.mock("@/hooks/use-mutations", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/hooks/use-mutations")>();
  return { ...actual, useWriteSA: vi.fn() };
});

// ── Fixtures ────────────────────────────────────────────────

const mockQG: SAQualityGate = {
  overall_score: 0.74,
  passed: true,
  section_completeness: 0.9,
  key_figure_coverage: 0.8,
  citation_accuracy: 0.72,
  citation_density: 0.65,
  admin_coverage: 0.7,
  date_attribution: 0.68,
};

const failQG: SAQualityGate = {
  overall_score: 0.42,
  passed: false,
  section_completeness: 0.4,
  key_figure_coverage: 0.3,
  citation_accuracy: 0.5,
  citation_density: 0.45,
  admin_coverage: 0.38,
  date_attribution: 0.55,
};

const mockSAResult: SAResponse = {
  markdown:
    "# Situation Analysis\n\n## Overview\n\nThis is a test report.\n\n## Impact\n\nDetails here.",
  output_file: "reports/situation-analysis-2026-test.md",
  quality_gate: mockQG,
  status: "ok",
};

/** Default stub so tests that don't care about mutation state don't crash. */
async function setDefaultWriteSAMock() {
  const { useWriteSA } = await import("@/hooks/use-mutations");
  vi.mocked(useWriteSA).mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    data: undefined,
    error: null,
  } as unknown as ReturnType<typeof useWriteSA>);
}

// ── SAQualityGateChart ───────────────────────────────────────

describe("SAQualityGateChart", () => {
  it("renders overall score percentage", () => {
    const { container } = renderWithProviders(
      <SAQualityGateChart qualityGate={mockQG} />
    );
    // Overall score: 0.74 * 100 = 74%
    expect(container.textContent).toContain("74.0%");
  });

  it("shows PASS badge when quality_gate.passed is true", () => {
    renderWithProviders(<SAQualityGateChart qualityGate={mockQG} />);
    expect(screen.getByText("PASS")).toBeInTheDocument();
  });

  it("shows FAIL badge when quality_gate.passed is false", () => {
    renderWithProviders(<SAQualityGateChart qualityGate={failQG} />);
    expect(screen.getByText("FAIL")).toBeInTheDocument();
  });

  it("renders without crashing when data has all 6 dimensions", () => {
    // Recharts SVG isn't rendered in JSDOM, but the component should not throw.
    expect(() =>
      renderWithProviders(<SAQualityGateChart qualityGate={mockQG} />)
    ).not.toThrow();
  });

  it("renders without crashing when all scores are zero", () => {
    const emptyQG: SAQualityGate = {
      overall_score: 0,
      passed: false,
      section_completeness: 0,
      key_figure_coverage: 0,
      citation_accuracy: 0,
      citation_density: 0,
      admin_coverage: 0,
      date_attribution: 0,
    };
    expect(() =>
      renderWithProviders(<SAQualityGateChart qualityGate={emptyQG} />)
    ).not.toThrow();
  });

  it("renders FAIL badge for low overall score", () => {
    const { container } = renderWithProviders(
      <SAQualityGateChart qualityGate={failQG} />
    );
    expect(screen.getByText("FAIL")).toBeInTheDocument();
    expect(container.textContent).toBeTruthy();
  });
});

// ── SAPage form ──────────────────────────────────────────────

describe("SAPage — form", () => {
  beforeEach(async () => {
    await setDefaultWriteSAMock();
  });

  it("renders the page title", () => {
    renderWithProviders(<SAPage />);
    expect(screen.getAllByText(/situation analysis/i).length).toBeGreaterThan(0);
  });

  it("shows the Generate button", () => {
    renderWithProviders(<SAPage />);
    expect(
      screen.getByRole("button", { name: /generate situation analysis/i })
    ).toBeInTheDocument();
  });

  it("shows all 4 template options", () => {
    renderWithProviders(<SAPage />);
    expect(screen.getByText("OCHA Full SA")).toBeInTheDocument();
    expect(screen.getByText("Default Report")).toBeInTheDocument();
    expect(screen.getByText("Brief Update")).toBeInTheDocument();
    expect(screen.getByText("Detailed Brief")).toBeInTheDocument();
  });

  it("shows Event Name input", () => {
    renderWithProviders(<SAPage />);
    expect(screen.getByLabelText(/event name/i)).toBeInTheDocument();
  });

  it("shows Event Type input", () => {
    renderWithProviders(<SAPage />);
    expect(screen.getByLabelText(/event type/i)).toBeInTheDocument();
  });

  it("shows Period input", () => {
    renderWithProviders(<SAPage />);
    expect(screen.getByLabelText(/period/i)).toBeInTheDocument();
  });

  it("shows LLM toggle", () => {
    renderWithProviders(<SAPage />);
    expect(screen.getByLabelText(/use llm/i)).toBeInTheDocument();
  });

  it("shows Quality gate toggle", () => {
    renderWithProviders(<SAPage />);
    expect(screen.getByLabelText(/quality gate scoring/i)).toBeInTheDocument();
  });

  it("shows Max Events, Max Cycles, Max Age inputs", () => {
    renderWithProviders(<SAPage />);
    expect(screen.getByLabelText(/max events/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/max cycles/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/max age/i)).toBeInTheDocument();
  });
});

// ── SAPage — output panel (mocked mutation result) ───────────

describe("SAPage — output panel", () => {
  it("does not show export buttons before running", async () => {
    await setDefaultWriteSAMock();
    renderWithProviders(<SAPage />);
    expect(screen.queryByRole("button", { name: /^markdown$/i })).toBeNull();
  });

  it("shows loading state while mutation is pending", async () => {
    const { useWriteSA } = await import("@/hooks/use-mutations");
    vi.mocked(useWriteSA).mockReturnValue({
      mutate: vi.fn(),
      isPending: true,
      isError: false,
      data: undefined,
      error: null,
    } as unknown as ReturnType<typeof useWriteSA>);

    renderWithProviders(<SAPage />);
    expect(screen.getByText(/running situation analysis/i)).toBeInTheDocument();
  });

  it("shows Markdown and HTML export buttons after a result", async () => {
    const { useWriteSA } = await import("@/hooks/use-mutations");
    vi.mocked(useWriteSA).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      isError: false,
      data: mockSAResult,
      error: null,
    } as unknown as ReturnType<typeof useWriteSA>);

    renderWithProviders(<SAPage />);
    const mdBtns = screen.getAllByRole("button", { name: /markdown/i });
    expect(mdBtns.length).toBeGreaterThan(0);
    const htmlBtns = screen.getAllByRole("button", { name: /html/i });
    expect(htmlBtns.length).toBeGreaterThan(0);
  });

  it("shows PASS quality gate badge when result has passing gate", async () => {
    const { useWriteSA } = await import("@/hooks/use-mutations");
    vi.mocked(useWriteSA).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      isError: false,
      data: mockSAResult,
      error: null,
    } as unknown as ReturnType<typeof useWriteSA>);

    renderWithProviders(<SAPage />);
    // PASS appears in both quality gate chart and in the page header badge
    const passBadges = screen.getAllByText("PASS");
    expect(passBadges.length).toBeGreaterThan(0);
  });

  it("shows output filename in panel header", async () => {
    const { useWriteSA } = await import("@/hooks/use-mutations");
    vi.mocked(useWriteSA).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      isError: false,
      data: mockSAResult,
      error: null,
    } as unknown as ReturnType<typeof useWriteSA>);

    renderWithProviders(<SAPage />);
    expect(screen.getByText("situation-analysis-2026-test.md")).toBeInTheDocument();
  });

  it("shows Sections tab when markdown has headings", async () => {
    const { useWriteSA } = await import("@/hooks/use-mutations");
    vi.mocked(useWriteSA).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      isError: false,
      data: mockSAResult,
      error: null,
    } as unknown as ReturnType<typeof useWriteSA>);

    renderWithProviders(<SAPage />);
    // markdown has 3 headings: #, ##, ## → "Sections (3)"
    expect(screen.getByText(/sections \(3\)/i)).toBeInTheDocument();
  });

  it("shows error message when mutation fails", async () => {
    const { useWriteSA } = await import("@/hooks/use-mutations");
    vi.mocked(useWriteSA).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      isError: true,
      data: undefined,
      error: new Error("LLM timeout"),
    } as unknown as ReturnType<typeof useWriteSA>);

    renderWithProviders(<SAPage />);
    expect(screen.getByText(/llm timeout/i)).toBeInTheDocument();
  });
});
