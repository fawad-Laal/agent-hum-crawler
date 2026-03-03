import { useReports } from "@/hooks/use-queries";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { FileText } from "lucide-react";
import { fmtRelativeTime } from "@/lib/utils";
import { useNavigate } from "react-router-dom";
import type { KeyboardEvent } from "react";

export function ReportsPage() {
  const { data: reports, isLoading, error } = useReports();
  const navigate = useNavigate();

  const openReport = (name: string) => {
    // Phase 4 will add a full report detail route; for now navigate with search param
    void navigate(`/reports?view=${encodeURIComponent(name)}`);
  };

  const handleKeyDown = (e: KeyboardEvent, name: string) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      openReport(name);
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-primary" />
            Generated Reports
            {reports && (
              <Badge variant="secondary" className="ml-2">
                {reports.length}
              </Badge>
            )}
          </CardTitle>
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

          {reports && reports.length === 0 && (
            <p className="text-muted-foreground">
              No reports generated yet. Run a report from the Operations page.
            </p>
          )}

          {reports && reports.length > 0 && (
            <div className="space-y-2">
              {reports.map((r) => (
                <div
                  key={r.name}
                  role="button"
                  tabIndex={0}
                  onClick={() => openReport(r.name)}
                  onKeyDown={(e) => handleKeyDown(e, r.name)}
                  className="flex items-center justify-between rounded-lg border border-border bg-muted/20 px-4 py-3 transition-colors hover:bg-muted/40 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <div className="flex items-center gap-3">
                    <FileText className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-medium">{r.name}</span>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-xs text-muted-foreground">
                      {(r.size / 1024).toFixed(1)} KB
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {fmtRelativeTime(r.modified)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <p className="text-xs text-muted-foreground">
        Full report preview, markdown rendering, and export (PDF/DOCX) will be
        added in Phase 4.
      </p>
    </div>
  );
}
