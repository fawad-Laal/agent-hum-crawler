import { Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "./sidebar";
import { Header } from "./header";
import { ErrorBoundary } from "./error-boundary";
import { useUIStore } from "@/stores/ui-store";
import { cn } from "@/lib/utils";
import { useEffect } from "react";

const routeTitles: Record<string, string> = {
  "/": "Overview",
  "/operations": "Operations",
  "/reports": "Reports",
  "/sources": "Source Intelligence",
  "/system": "System Health",
  "/sa": "Situation Analysis",
  "/settings": "Settings",
};

export function RootLayout() {
  const sidebarOpen = useUIStore((s) => s.sidebarOpen);
  const location = useLocation();

  const title = routeTitles[location.pathname] ?? "Agent HUM Crawler";

  useEffect(() => {
    document.title = `${title} — Agent HUM`;
  }, [title]);

  return (
    <div className="flex min-h-screen">
      <Sidebar />

      <div
        className={cn(
          "flex flex-1 flex-col transition-all duration-300",
          sidebarOpen ? "ml-60" : "ml-16"
        )}
      >
        <Header title={title} />

        <main className="flex-1 overflow-y-auto px-6 py-6">
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
