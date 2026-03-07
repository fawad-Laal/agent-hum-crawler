/**
 * Phase 10.1 — Layout Components Tests
 * Covers: ErrorBoundary, Header, Sidebar, RootLayout, GlobalJobBadge
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { ErrorBoundary } from "@/components/layout/error-boundary";
import { Header } from "@/components/layout/header";
import { Sidebar } from "@/components/layout/sidebar";
import { RootLayout } from "@/components/layout/root-layout";
import { GlobalJobBadge } from "@/components/ui/global-job-badge";
import { useJobsStore } from "@/stores/jobs-store";
import { useUIStore } from "@/stores/ui-store";
import * as queries from "@/hooks/use-queries";

// ── Module mock: replace useHealth with a vi.fn (synchronous factory) ──
vi.mock("@/hooks/use-queries", () => ({
  useHealth: vi.fn(),
}));

// ── Helpers ────────────────────────────────────────────────────

function makeQC() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
}

function withQC(ui: ReactNode, qc?: QueryClient) {
  const client = qc ?? makeQC();
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

function withRouter(ui: ReactNode, path = "/") {
  return render(
    <QueryClientProvider client={makeQC()}>
      <MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

/** Render RootLayout inside a proper route tree so <Outlet /> works. */
function renderLayout(path = "/") {
  const qc = makeQC();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/" element={<RootLayout />}>
            <Route index element={<div>home content</div>} />
            <Route path="operations" element={<div>ops content</div>} />
            <Route path="reports" element={<div>reports content</div>} />
            <Route path="sources" element={<div>sources content</div>} />
            <Route path="sa" element={<div>sa content</div>} />
            <Route path="settings" element={<div>settings content</div>} />
            <Route path="unknown-page" element={<div>unknown</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// ═══════════════════════════════════════════════════════════════
// GlobalJobBadge
// ═══════════════════════════════════════════════════════════════

describe("GlobalJobBadge", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useJobsStore.setState({ jobs: {} });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders nothing when no active jobs", () => {
    const { container } = render(<GlobalJobBadge />);
    expect(container.firstChild).toBeNull();
  });

  it("shows label when a single job is active", () => {
    useJobsStore.setState({
      jobs: {
        "job-1": { id: "job-1", label: "Running cycle", status: "running", startedAt: Date.now() },
      },
    });
    render(<GlobalJobBadge />);
    expect(screen.getByText(/Running cycle/)).toBeInTheDocument();
  });

  it("shows elapsed seconds in label", () => {
    const startedAt = Date.now();
    useJobsStore.setState({
      jobs: {
        "job-1": { id: "job-1", label: "Running cycle", status: "running", startedAt },
      },
    });
    render(<GlobalJobBadge />);

    // Advance 5 seconds inside act so React flushes the state update from setInterval
    act(() => { vi.advanceTimersByTime(5_000); });

    // The component should show "· 5s"
    expect(screen.getByText(/· 5s/)).toBeInTheDocument();
  });

  it("shows multi-job label when more than one active job", () => {
    const now = Date.now();
    useJobsStore.setState({
      jobs: {
        "job-1": { id: "job-1", label: "Running cycle", status: "running", startedAt: now },
        "job-2": { id: "job-2", label: "Generating report", status: "queued", startedAt: now },
      },
    });
    render(<GlobalJobBadge />);
    expect(screen.getByText(/2 jobs running/)).toBeInTheDocument();
  });

  it("renders nothing for completed/failed jobs", () => {
    useJobsStore.setState({
      jobs: {
        "job-1": { id: "job-1", label: "Done", status: "done", startedAt: Date.now() - 10_000 },
        "job-2": { id: "job-2", label: "Failed", status: "error", startedAt: Date.now() - 5_000 },
      },
    });
    const { container } = render(<GlobalJobBadge />);
    expect(container.firstChild).toBeNull();
  });
});

// ═══════════════════════════════════════════════════════════════
// ErrorBoundary
// ═══════════════════════════════════════════════════════════════

// A component that always throws during render
function PanicButton({ message }: { message: string }) {
  throw new Error(message);
}

describe("ErrorBoundary", () => {
  beforeEach(() => {
    // Suppress the React error boundary console noise
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders children normally when there is no error", () => {
    render(
      <ErrorBoundary>
        <span>safe content</span>
      </ErrorBoundary>,
    );
    expect(screen.getByText("safe content")).toBeInTheDocument();
  });

  it("renders default error UI when a child throws", () => {
    render(
      <ErrorBoundary>
        <PanicButton message="something broke" />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(screen.getByText(/something broke/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Try again/i })).toBeInTheDocument();
  });

  it("resets the error state when Try again is clicked", () => {
    const { rerender } = render(
      <ErrorBoundary>
        <PanicButton message="boom" />
      </ErrorBoundary>,
    );
    // Error UI is shown
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();

    // Switch children to safe content BEFORE clicking reset, so the ErrorBoundary
    // won't throw again when it re-renders after handleReset clears hasError.
    rerender(
      <ErrorBoundary>
        <span>recovered</span>
      </ErrorBoundary>,
    );

    // Click the reset button — this clears hasError and re-renders safe children
    fireEvent.click(screen.getByRole("button", { name: /Try again/i }));

    expect(screen.getByText("recovered")).toBeInTheDocument();
  });

  it("renders custom fallback when provided", () => {
    render(
      <ErrorBoundary fallback={<div>custom fallback</div>}>
        <PanicButton message="exploded" />
      </ErrorBoundary>,
    );
    expect(screen.getByText("custom fallback")).toBeInTheDocument();
    expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();
  });
});

// ═══════════════════════════════════════════════════════════════
// Header
// ═══════════════════════════════════════════════════════════════

describe("Header", () => {
  beforeEach(() => {
    useJobsStore.setState({ jobs: {} });
  });

  it("shows 'Checking…' while health is loading", () => {
    vi.mocked(queries.useHealth).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      isSuccess: false,
      isPending: true,
      isFetching: false,
    } as ReturnType<typeof queries.useHealth>);

    withQC(
      <MemoryRouter>
        <Header title="Test Page" />
      </MemoryRouter>,
    );

    expect(screen.getByText("Checking…")).toBeInTheDocument();
  });

  it("shows 'Backend Online' when health status is ok", () => {
    vi.mocked(queries.useHealth).mockReturnValue({
      data: { status: "ok" },
      isLoading: false,
      isError: false,
      isSuccess: true,
      isPending: false,
      isFetching: false,
    } as ReturnType<typeof queries.useHealth>);

    withQC(
      <MemoryRouter>
        <Header title="Dashboard" />
      </MemoryRouter>,
    );

    expect(screen.getByText("Backend Online")).toBeInTheDocument();
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
  });

  it("shows 'Backend Offline' when health status is not ok", () => {
    vi.mocked(queries.useHealth).mockReturnValue({
      data: { status: "error" },
      isLoading: false,
      isError: false,
      isSuccess: true,
      isPending: false,
      isFetching: false,
    } as ReturnType<typeof queries.useHealth>);

    withQC(
      <MemoryRouter>
        <Header title="Dashboard" />
      </MemoryRouter>,
    );

    expect(screen.getByText("Backend Offline")).toBeInTheDocument();
  });

  it("renders a refresh button", () => {
    vi.mocked(queries.useHealth).mockReturnValue({
      data: { status: "ok" },
      isLoading: false,
      isError: false,
      isSuccess: true,
      isPending: false,
      isFetching: false,
    } as ReturnType<typeof queries.useHealth>);

    withQC(
      <MemoryRouter>
        <Header title="Dashboard" />
      </MemoryRouter>,
    );

    expect(screen.getByRole("button", { name: /Refresh data/i })).toBeInTheDocument();
  });

  it("clicking refresh calls queryClient.invalidateQueries", () => {
    vi.mocked(queries.useHealth).mockReturnValue({
      data: { status: "ok" },
      isLoading: false,
    } as ReturnType<typeof queries.useHealth>);

    const qc = makeQC();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries").mockResolvedValue();

    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <Header title="Dashboard" />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: /Refresh data/i }));
    expect(invalidateSpy).toHaveBeenCalledTimes(1);
  });
});

// ═══════════════════════════════════════════════════════════════
// Sidebar
// ═══════════════════════════════════════════════════════════════

describe("Sidebar", () => {
  beforeEach(() => {
    useUIStore.setState({ sidebarOpen: true });
  });

  it("renders Main navigation landmark", () => {
    withRouter(<Sidebar />);
    // <aside aria-label="Main navigation"> has ARIA role "complementary"
    expect(screen.getByRole("complementary", { name: /Main navigation/i })).toBeInTheDocument();
  });

  it("shows all 8 nav labels when sidebar is open", () => {
    withRouter(<Sidebar />);
    expect(screen.getByText("Overview")).toBeInTheDocument();
    expect(screen.getByText("Operations")).toBeInTheDocument();
    expect(screen.getByText("Reports")).toBeInTheDocument();
    expect(screen.getByText("Sources")).toBeInTheDocument();
    expect(screen.getByText("Data")).toBeInTheDocument();
    expect(screen.getByText("System")).toBeInTheDocument();
    expect(screen.getByText("Situation Analysis")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("hides nav labels when sidebar is collapsed", () => {
    useUIStore.setState({ sidebarOpen: false });
    withRouter(<Sidebar />);
    expect(screen.queryByText("Overview")).not.toBeInTheDocument();
    expect(screen.queryByText("Operations")).not.toBeInTheDocument();
    expect(screen.queryByText("Settings")).not.toBeInTheDocument();
  });

  it("shows 'Agent HUM' brand label when open", () => {
    withRouter(<Sidebar />);
    expect(screen.getByText("Agent HUM")).toBeInTheDocument();
  });

  it("hides 'Agent HUM' brand label when collapsed", () => {
    useUIStore.setState({ sidebarOpen: false });
    withRouter(<Sidebar />);
    expect(screen.queryByText("Agent HUM")).not.toBeInTheDocument();
  });

  it("calls toggleSidebar when the chevron button is clicked", () => {
    const toggle = vi.fn();
    useUIStore.setState({ sidebarOpen: true, toggleSidebar: toggle });
    withRouter(<Sidebar />);

    const button = screen.getByRole("button");
    fireEvent.click(button);
    expect(toggle).toHaveBeenCalledOnce();
  });
});

// ═══════════════════════════════════════════════════════════════
// RootLayout
// ═══════════════════════════════════════════════════════════════

describe("RootLayout", () => {
  beforeEach(() => {
    useUIStore.setState({ sidebarOpen: true });
    useJobsStore.setState({ jobs: {} });
    // Health mock: always return ok so Header is stable
    vi.mocked(queries.useHealth).mockReturnValue({
      data: { status: "ok" },
      isLoading: false,
      isError: false,
      isSuccess: true,
      isPending: false,
      isFetching: false,
    } as ReturnType<typeof queries.useHealth>);
  });

  it("renders outlet content for the root path", async () => {
    renderLayout("/");
    await waitFor(() => expect(screen.getByText("home content")).toBeInTheDocument());
  });

  it("sets document.title to 'Overview — Agent HUM' at root", async () => {
    renderLayout("/");
    await waitFor(() =>
      expect(document.title).toBe("Overview — Agent HUM"),
    );
  });

  it("sets document.title to 'Operations — Agent HUM' at /operations", async () => {
    renderLayout("/operations");
    await waitFor(() =>
      expect(document.title).toBe("Operations — Agent HUM"),
    );
  });

  it("sets document.title to 'Situation Analysis — Agent HUM' at /sa", async () => {
    renderLayout("/sa");
    await waitFor(() =>
      expect(document.title).toBe("Situation Analysis — Agent HUM"),
    );
  });

  it("uses fallback title for unknown paths", async () => {
    render(
      <QueryClientProvider client={makeQC()}>
        <MemoryRouter initialEntries={["/unknown-page"]}>
          <Routes>
            <Route path="/" element={<RootLayout />}>
              <Route path="unknown-page" element={<div>unknown</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() =>
      expect(document.title).toBe("Agent HUM Crawler — Agent HUM"),
    );
  });

  it("adds ml-60 class to content wrapper when sidebar is open", async () => {
    useUIStore.setState({ sidebarOpen: true });
    const { container } = renderLayout("/");
    await waitFor(() => {
      const contentDiv = container.querySelector(".ml-60");
      expect(contentDiv).not.toBeNull();
    });
  });

  it("adds ml-16 class to content wrapper when sidebar is closed", async () => {
    useUIStore.setState({ sidebarOpen: false });
    const { container } = renderLayout("/");
    await waitFor(() => {
      const contentDiv = container.querySelector(".ml-16");
      expect(contentDiv).not.toBeNull();
    });
  });
});
