import { createBrowserRouter } from "react-router-dom";
import { RootLayout } from "@/components/layout/root-layout";
import { OverviewPage } from "@/features/overview/overview-page";
import { OperationsPage } from "@/features/operations/operations-page";
import { ReportsPage } from "@/features/reports/reports-page";
import { SourcesPage } from "@/features/sources/sources-page";
import { SystemPage } from "@/features/system/system-page";
import { SAPage } from "@/features/situation-analysis/sa-page";
import { SettingsPage } from "@/features/settings/settings-page";
import { NotFoundPage } from "@/features/not-found/not-found-page";

export const router = createBrowserRouter(
  [
    {
      path: "/",
      element: <RootLayout />,
      children: [
        { index: true, element: <OverviewPage /> },
        { path: "operations", element: <OperationsPage /> },
        { path: "reports", element: <ReportsPage /> },
        { path: "sources", element: <SourcesPage /> },
        { path: "system", element: <SystemPage /> },
        { path: "sa", element: <SAPage /> },
        { path: "settings", element: <SettingsPage /> },
        { path: "*", element: <NotFoundPage /> },
      ],
    },
  ],
  {
    basename: "/v2",
  }
);
