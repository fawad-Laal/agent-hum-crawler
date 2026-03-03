/**
 * Project Phoenix — Phase 4 Reports Module Tests
 * Tests report detail page, reports page with tabs, markdown renderer,
 * and preset modal rendering.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor, fireEvent } from "@testing-library/react";
import { renderWithProviders } from "../test-utils";
import { ReportsPage } from "@/features/reports/reports-page";
import { ReportDetailPage } from "@/features/reports/report-detail-page";
import { MarkdownRenderer } from "@/components/ui/markdown-renderer";

// ── Mock API ────────────────────────────────────────────────

const mockReports = [
  { name: "report-20260302T091804Z.md", size: 8192, modified: "2026-03-02T09:18:04Z" },
  { name: "situation-analysis-20260220T082307Z.md", size: 4096, modified: "2026-02-20T08:23:07Z" },
  { name: "report-20260220T133332Z.md", size: 6144, modified: "2026-02-20T13:33:32Z" },
  { name: "report-20260219T225419Z.md", size: 5120, modified: "2026-02-19T22:54:19Z" },
  { name: "report-20260219T233238Z.md", size: 7168, modified: "2026-02-19T23:32:38Z" },
  { name: "report-20260218T155012Z.md", size: 4608, modified: "2026-02-18T15:50:12Z" },
];

const mockReportDetail = {
  name: "report-20260302T091804Z.md",
  markdown: "# Test Report\n\n## Executive Summary\n\nThis is a test report.\n\n## Key Figures\n\n| Indicator | Value |\n|-----------|-------|\n| Deaths | 10 |\n| Displaced | 5000 |",
};

vi.mock("@/lib/api", () => ({
  fetchReports: vi.fn(() => Promise.resolve(mockReports)),
  fetchReport: vi.fn(() => Promise.resolve(mockReportDetail)),
  fetchOverview: vi.fn(() => Promise.resolve({})),
  fetchHealth: vi.fn(() => Promise.resolve({ status: "ok" })),
  fetchWorkbenchProfiles: vi.fn(() =>
    Promise.resolve({ presets: {}, last_profile: null })
  ),
  fetchSystemInfo: vi.fn(() =>
    Promise.resolve({
      python_version: "3.12",
      rust_available: true,
      allowed_disaster_types: ["flood"],
    })
  ),
  fetchCountrySources: vi.fn(() =>
    Promise.resolve({ countries: [], global_feed_count: 0, global_sources: {} })
  ),
}));

// Suppress react-router complaints in test
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...(actual as Record<string, unknown>),
    useParams: () => ({ name: "report-20260302T091804Z.md" }),
    useNavigate: () => vi.fn(),
  };
});

// ── Tests ───────────────────────────────────────────────────

describe("MarkdownRenderer", () => {
  it("renders markdown content with headings", () => {
    const md = `# Hello World

Some text`;
    renderWithProviders(
      <MarkdownRenderer content={md} />,
    );
    expect(screen.getByText("Hello World")).toBeInTheDocument();
    expect(screen.getByText("Some text")).toBeInTheDocument();
  });

  it("renders GFM tables", () => {
    const md = "| Col A | Col B |\n|-------|-------|\n| 1 | 2 |";
    renderWithProviders(<MarkdownRenderer content={md} />);
    expect(screen.getByText("Col A")).toBeInTheDocument();
    expect(screen.getByText("Col B")).toBeInTheDocument();
  });

  it("renders in compact mode without errors", () => {
    const md = `## Compact

Test`;
    renderWithProviders(
      <MarkdownRenderer content={md} compact />,
    );
    expect(screen.getByText("Compact")).toBeInTheDocument();
  });

  it("renders inline code and blockquotes", () => {
    const md = "> Important note\n\nUse `format()` here";
    renderWithProviders(<MarkdownRenderer content={md} />);
    expect(screen.getByText("Important note")).toBeInTheDocument();
    expect(screen.getByText(/format\(\)/)).toBeInTheDocument();
  });

  it("renders lists properly", () => {
    const md = "- Item A\n- Item B\n- Item C";
    renderWithProviders(<MarkdownRenderer content={md} />);
    expect(screen.getByText("Item A")).toBeInTheDocument();
    expect(screen.getByText("Item C")).toBeInTheDocument();
  });

  it("renders empty content without crashing", () => {
    renderWithProviders(<MarkdownRenderer content="" />);
    // Should not throw — just renders an empty prose container
  });
});

describe("ReportsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders tab headers for Reports and Workbench", async () => {
    renderWithProviders(<ReportsPage />, { initialRoute: "/reports" });
    await waitFor(() => {
      expect(screen.getByRole("tab", { name: /reports/i })).toBeInTheDocument();
      expect(screen.getByRole("tab", { name: /workbench/i })).toBeInTheDocument();
    });
  });

  it("displays report listing after data loads", async () => {
    renderWithProviders(<ReportsPage />, { initialRoute: "/reports" });
    await waitFor(() => {
      expect(screen.getByText("report-20260302T091804Z.md")).toBeInTheDocument();
    });
  });

  it("shows SA badge for situation analysis reports", async () => {
    renderWithProviders(<ReportsPage />, { initialRoute: "/reports" });
    await waitFor(() => {
      expect(screen.getByText("SA")).toBeInTheDocument();
    });
  });

  it("shows report count badge", async () => {
    renderWithProviders(<ReportsPage />, { initialRoute: "/reports" });
    await waitFor(() => {
      expect(screen.getByText("6")).toBeInTheDocument();
    });
  });

  it("filters reports when search input is used", async () => {
    renderWithProviders(<ReportsPage />, { initialRoute: "/reports" });
    await waitFor(() => {
      expect(screen.getByText("report-20260302T091804Z.md")).toBeInTheDocument();
    });
    const searchInput = screen.getByPlaceholderText("Filter reports…");
    fireEvent.change(searchInput, { target: { value: "situation" } });
    expect(screen.queryByText("report-20260302T091804Z.md")).not.toBeInTheDocument();
    expect(screen.getByText("situation-analysis-20260220T082307Z.md")).toBeInTheDocument();
  });

  it("shows no-match message when filter yields zero results", async () => {
    renderWithProviders(<ReportsPage />, { initialRoute: "/reports" });
    await waitFor(() => {
      expect(screen.getByText("report-20260302T091804Z.md")).toBeInTheDocument();
    });
    const searchInput = screen.getByPlaceholderText("Filter reports…");
    fireEvent.change(searchInput, { target: { value: "nonexistent" } });
    expect(screen.getByText("No reports match the filter.")).toBeInTheDocument();
  });
});

describe("ReportDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders report name and back button", async () => {
    renderWithProviders(<ReportDetailPage />, { initialRoute: "/reports/report-20260302T091804Z.md" });
    await waitFor(() => {
      expect(screen.getByText("Reports")).toBeInTheDocument();
    });
  });

  it("shows export buttons after report loads", async () => {
    renderWithProviders(<ReportDetailPage />, { initialRoute: "/reports/report-20260302T091804Z.md" });
    await waitFor(() => {
      expect(screen.getByText("Markdown")).toBeInTheDocument();
      expect(screen.getByText("HTML")).toBeInTheDocument();
      expect(screen.getByText("JSON")).toBeInTheDocument();
    });
  });

  it("renders markdown content of the report", async () => {
    renderWithProviders(<ReportDetailPage />, { initialRoute: "/reports/report-20260302T091804Z.md" });
    await waitFor(() => {
      expect(screen.getByText("Test Report")).toBeInTheDocument();
      expect(screen.getByText("Executive Summary")).toBeInTheDocument();
    });
  });

  it("shows word count and section count badges", async () => {
    renderWithProviders(<ReportDetailPage />, { initialRoute: "/reports/report-20260302T091804Z.md" });
    await waitFor(() => {
      // report-detail-page computes word count and section count
      expect(screen.getByText("Report")).toBeInTheDocument();
      expect(screen.getByText(/sections/)).toBeInTheDocument();
      expect(screen.getByText(/words/)).toBeInTheDocument();
    });
  });

  it("shows copy markdown button", async () => {
    renderWithProviders(<ReportDetailPage />, { initialRoute: "/reports/report-20260302T091804Z.md" });
    await waitFor(() => {
      expect(screen.getByText("Copy MD")).toBeInTheDocument();
    });
  });

  it("renders the report type badge correctly for standard reports", async () => {
    renderWithProviders(<ReportDetailPage />, { initialRoute: "/reports/report-20260302T091804Z.md" });
    await waitFor(() => {
      expect(screen.getByText("Report")).toBeInTheDocument();
    });
  });
});
