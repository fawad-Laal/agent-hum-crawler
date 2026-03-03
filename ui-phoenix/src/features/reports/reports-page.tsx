/**
 * Project Phoenix — Phase 4 Reports Page
 * Tabbed layout: Report Listing (virtualized) + Workbench.
 * Report list uses React Virtuoso for 1000+ report scale.
 * Clicking a report navigates to /reports/:name detail view.
 */

import { useReports } from "@/hooks/use-queries";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { FileText, FlaskConical, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { fmtRelativeTime } from "@/lib/utils";
import { useNavigate } from "react-router-dom";
import { useState, useMemo, useCallback } from "react";
import type { KeyboardEvent } from "react";
import { Virtuoso } from "react-virtuoso";
import { ReportWorkbench } from "./report-workbench";
import type { ReportListItem } from "@/types";

// ── Virtualized Report Row ──────────────────────────────────

function ReportRow({
  report,
  onClick,
}: {
  report: ReportListItem;
  onClick: () => void;
}) {
  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onClick();
    }
  };

  const isSA = report.name.startsWith("situation-analysis-");

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={handleKeyDown}
      className="flex items-center justify-between rounded-lg border border-border bg-muted/20 px-4 py-3 transition-colors hover:bg-muted/40 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring mb-2"
    >
      <div className="flex items-center gap-3 min-w-0">
        <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
        <span className="text-sm font-medium truncate">{report.name}</span>
        {isSA && (
          <Badge variant="secondary" className="text-[10px] shrink-0">
            SA
          </Badge>
        )}
      </div>
      <div className="flex items-center gap-4 shrink-0">
        <span className="text-xs text-muted-foreground tabular-nums">
          {(report.size / 1024).toFixed(1)} KB
        </span>
        <span className="text-xs text-muted-foreground">
          {fmtRelativeTime(report.modified)}
        </span>
      </div>
    </div>
  );
}

// ── Main Reports Page ───────────────────────────────────────

export function ReportsPage() {
  const { data: reports, isLoading, error } = useReports();
  const navigate = useNavigate();
  const [filter, setFilter] = useState("");

  const filteredReports = useMemo(() => {
    if (!reports) return [];
    if (!filter.trim()) return reports;
    const q = filter.toLowerCase();
    return reports.filter((r) => r.name.toLowerCase().includes(q));
  }, [reports, filter]);

  const openReport = useCallback(
    (name: string) => {
      void navigate(`/reports/${encodeURIComponent(name)}`);
    },
    [navigate],
  );

  // Use virtualized list when over 50 items, otherwise render normally
  const useVirtualized = filteredReports.length > 50;

  return (
    <Tabs defaultValue="listing" className="space-y-4">
      <TabsList>
        <TabsTrigger value="listing">
          <FileText className="h-4 w-4 mr-1.5" />
          Reports
        </TabsTrigger>
        <TabsTrigger value="workbench">
          <FlaskConical className="h-4 w-4 mr-1.5" />
          Workbench
        </TabsTrigger>
      </TabsList>

      {/* ── Reports Listing Tab ──────────────────────────── */}
      <TabsContent value="listing">
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between gap-4">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="h-5 w-5 text-primary" />
                  Generated Reports
                  {reports && (
                    <Badge variant="secondary" className="ml-2">
                      {filteredReports.length}
                      {filter && ` / ${reports.length}`}
                    </Badge>
                  )}
                </CardTitle>
                <CardDescription className="mt-1">
                  Click a report to view full content with markdown rendering and export options.
                </CardDescription>
              </div>
              {reports && reports.length > 5 && (
                <div className="relative w-64 shrink-0">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    placeholder="Filter reports…"
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                    className="pl-9 h-9"
                  />
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {error && (
              <p className="text-destructive text-sm">
                Failed to load reports: {error.message}
              </p>
            )}

            {isLoading && (
              <div className="space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            )}

            {reports && filteredReports.length === 0 && (
              <p className="text-muted-foreground text-sm py-4">
                {filter
                  ? "No reports match the filter."
                  : "No reports generated yet. Run a report from the Operations page."}
              </p>
            )}

            {/* Virtualized list for scale (50+ items) */}
            {filteredReports.length > 0 && useVirtualized && (
              <Virtuoso
                key={filter}
                style={{ height: "600px" }}
                totalCount={filteredReports.length}
                itemContent={(index) => {
                  const r = filteredReports[index];
                  return (
                    <ReportRow
                      report={r}
                      onClick={() => openReport(r.name)}
                    />
                  );
                }}
              />
            )}

            {/* Standard list for smaller sets */}
            {filteredReports.length > 0 && !useVirtualized && (
              <div className="space-y-0">
                {filteredReports.map((r) => (
                  <ReportRow
                    key={r.name}
                    report={r}
                    onClick={() => openReport(r.name)}
                  />
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </TabsContent>

      {/* ── Workbench Tab ────────────────────────────────── */}
      <TabsContent value="workbench">
        <ReportWorkbench />
      </TabsContent>
    </Tabs>
  );
}
