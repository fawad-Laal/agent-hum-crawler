import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../test-utils";
import { OverviewPage } from "@/features/overview/overview-page";
import { OperationsPage } from "@/features/operations/operations-page";
import { ReportsPage } from "@/features/reports/reports-page";
import { SourcesPage } from "@/features/sources/sources-page";
import { SystemPage } from "@/features/system/system-page";
import { SAPage } from "@/features/situation-analysis/sa-page";
import { SettingsPage } from "@/features/settings/settings-page";

describe("Route smoke tests", () => {
  it("renders OverviewPage without crashing", () => {
    renderWithProviders(<OverviewPage />);
    expect(screen.getByText("Key Metrics")).toBeInTheDocument();
  });

  it("renders OperationsPage without crashing", () => {
    renderWithProviders(<OperationsPage />);
    expect(screen.getByText("Command Center")).toBeInTheDocument();
  });

  it("renders ReportsPage without crashing", () => {
    renderWithProviders(<ReportsPage />);
    expect(screen.getByText("Generated Reports")).toBeInTheDocument();
  });

  it("renders SourcesPage without crashing", () => {
    renderWithProviders(<SourcesPage />);
    expect(screen.getByText("Source Intelligence")).toBeInTheDocument();
  });

  it("renders SystemPage without crashing", () => {
    renderWithProviders(<SystemPage />);
    expect(screen.getByText("E2E Gate Summary")).toBeInTheDocument();
  });

  it("renders SAPage without crashing", () => {
    renderWithProviders(<SAPage />);
    expect(screen.getByText("Situation Analysis")).toBeInTheDocument();
  });

  it("renders SettingsPage without crashing", () => {
    renderWithProviders(<SettingsPage />);
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });
});
