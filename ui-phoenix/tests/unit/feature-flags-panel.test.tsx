/**
 * Phase 10A.2 — FeatureFlagsPanel rendering tests
 * Verifies type-aware boolean coercion fix:
 *   - Boolean("false") === true  (old broken behaviour)
 *   - "false" → unchecked Switch (correct)
 *   - "0"     → unchecked Switch (correct)
 *   - non-bool-like string → Badge, not Switch
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { FeatureFlagsPanel } from "@/features/system/feature-flags-panel";

// ── suppress noisy console output ──────────────────────────────

beforeEach(() => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  vi.spyOn(console, "warn").mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ── wrapper ────────────────────────────────────────────────────

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

function renderPanel(flags: Record<string, boolean | number | string>) {
  return render(
    <FeatureFlagsPanel flags={flags} isLoading={false} />,
    { wrapper: makeWrapper() },
  );
}

// ═══════════════════════════════════════════════════════════════
// 10A.2 — Boolean coercion tests
// ═══════════════════════════════════════════════════════════════

describe("FeatureFlagsPanel — boolean coercion (10A.2)", () => {
  it('renders a Switch for boolean true flag in enabled state', () => {
    renderPanel({ use_llm: true });
    // Single flag rendered — no name filter needed
    const sw = screen.getByRole("switch");
    expect(sw).toBeChecked();
  });

  it('renders a Switch for boolean false flag in disabled state', () => {
    renderPanel({ use_llm: false });
    const sw = screen.getByRole("switch");
    expect(sw).not.toBeChecked();
  });

  it('renders a Switch for numeric 1 (truthy) in enabled state', () => {
    renderPanel({ debug_mode: 1 });
    const sw = screen.getByRole("switch");
    expect(sw).toBeChecked();
  });

  it('renders a Switch for numeric 0 (falsy) in disabled state', () => {
    renderPanel({ debug_mode: 0 });
    const sw = screen.getByRole("switch");
    expect(sw).not.toBeChecked();
  });

  it('10A.2: "false" string → unchecked Switch (not true!)', () => {
    // Old bug: Boolean("false") === true → switch was checked
    renderPanel({ use_llm: "false" });
    const sw = screen.getByRole("switch");
    expect(sw).not.toBeChecked();
  });

  it('10A.2: "0" string → unchecked Switch (not true!)', () => {
    // Old bug: Boolean("0") === true → switch was checked
    renderPanel({ cache_sources: "0" });
    const sw = screen.getByRole("switch");
    expect(sw).not.toBeChecked();
  });

  it('10A.2: "true" string → checked Switch', () => {
    renderPanel({ quality_gate: "true" });
    const sw = screen.getByRole("switch");
    expect(sw).toBeChecked();
  });

  it('10A.2: non-bool-like string → renders Badge, not Switch', () => {
    renderPanel({ custom_model: "gpt-4o" });
    // No switch rendered for non-bool-like flags
    expect(screen.queryByRole("switch")).toBeNull();
    // The raw value should appear as text content
    expect(screen.getByText("gpt-4o")).toBeDefined();
  });

  it('10A.2: non-bool-like numeric string \u2192 renders Badge', () => {
    renderPanel({ timeout_seconds: "300" });
    expect(screen.queryByRole("switch")).toBeNull();
    expect(screen.getByText("300")).toBeDefined();
  });
});

// ═══════════════════════════════════════════════════════════════
// Structural / UX tests
// ═══════════════════════════════════════════════════════════════

describe("FeatureFlagsPanel — structure", () => {
  it("renders loading skeletons when isLoading is true", () => {
    const { container } = render(
      <FeatureFlagsPanel flags={undefined} isLoading={true} />,
      { wrapper: makeWrapper() },
    );
    expect(screen.queryByRole("switch")).toBeNull();
    // Skeleton renders a plain <div class="animate-pulse ..."> — no data-slot attribute
    expect(container.querySelector('.animate-pulse')).not.toBeNull();
  });

  it("renders empty state message when flags is empty", () => {
    renderPanel({});
    expect(screen.getByText(/no feature flags configured/i)).toBeDefined();
  });

  it("renders all flags alphabetically", () => {
    renderPanel({ zzz_flag: false, aaa_flag: true });
    const switches = screen.getAllByRole("switch");
    const labels = switches.map((s) => s.getAttribute("aria-label") ?? "");
    // aaa comes before zzz alphabetically
    expect(labels[0]).toContain("aaa_flag");
    expect(labels[1]).toContain("zzz_flag");
  });
});
