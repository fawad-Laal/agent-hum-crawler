import { createBrowserRouter } from "react-router-dom";
import { lazy, Suspense } from "react";
import { RootLayout } from "@/components/layout/root-layout";
import { OverviewPage } from "@/features/overview/overview-page";
import { NotFoundPage } from "@/features/not-found/not-found-page";

// Lazy-loaded feature pages (code-split)
const OperationsPage = lazy(() => import("@/features/operations/operations-page").then(m => ({ default: m.OperationsPage })));
const ReportsPage = lazy(() => import("@/features/reports/reports-page").then(m => ({ default: m.ReportsPage })));
const ReportDetailPage = lazy(() => import("@/features/reports/report-detail-page").then(m => ({ default: m.ReportDetailPage })));
const SourcesPage = lazy(() => import("@/features/sources/sources-page").then(m => ({ default: m.SourcesPage })));
const SystemPage = lazy(() => import("@/features/system/system-page").then(m => ({ default: m.SystemPage })));
const SAPage = lazy(() => import("@/features/situation-analysis/sa-page").then(m => ({ default: m.SAPage })));
const SettingsPage = lazy(() => import("@/features/settings/settings-page").then(m => ({ default: m.SettingsPage })));

function LazyWrap({ children }: { children: React.ReactNode }) {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      {children}
    </Suspense>
  );
}

export const router = createBrowserRouter(
  [
    {
      path: "/",
      element: <RootLayout />,
      children: [
        { index: true, element: <OverviewPage /> },
        { path: "operations", element: <LazyWrap><OperationsPage /></LazyWrap> },
        { path: "reports", element: <LazyWrap><ReportsPage /></LazyWrap> },
        { path: "reports/:name", element: <LazyWrap><ReportDetailPage /></LazyWrap> },
        { path: "sources", element: <LazyWrap><SourcesPage /></LazyWrap> },
        { path: "system", element: <LazyWrap><SystemPage /></LazyWrap> },
        { path: "sa", element: <LazyWrap><SAPage /></LazyWrap> },
        { path: "settings", element: <LazyWrap><SettingsPage /></LazyWrap> },
        { path: "*", element: <NotFoundPage /> },
      ],
    },
  ],
);
