/**
 * SourceHealthTable — tabular display of source-check results
 * Shows per-source status, freshness badge, fetched/matched counts,
 * age, and stale streak with colour-coded freshness indicators.
 */

import { Badge } from "@/components/ui/badge";
import type { SourceCheckResult } from "@/types";
import { cn } from "@/lib/utils";

interface SourceHealthTableProps {
  sources: SourceCheckResult[];
}

const freshnessVariant = (
  status: string
): "success" | "warning" | "destructive" | "secondary" => {
  if (status === "fresh") return "success";
  if (status === "aging") return "warning";
  if (status === "stale") return "destructive";
  return "secondary";
};

const statusDot = (working: boolean) => (
  <span
    className={cn(
      "inline-block h-2 w-2 rounded-full flex-shrink-0",
      working ? "bg-status-pass" : "bg-status-fail"
    )}
    aria-label={working ? "working" : "failing"}
  />
);

export function SourceHealthTable({ sources }: SourceHealthTableProps) {
  if (!sources.length) {
    return (
      <p className="text-sm text-muted-foreground py-4 text-center">
        No source results to display.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border text-muted-foreground">
            <th className="py-2 pr-3 text-left font-medium">Source</th>
            <th className="py-2 pr-3 text-left font-medium">Connector</th>
            <th className="py-2 pr-3 text-center font-medium">Status</th>
            <th className="py-2 pr-3 text-right font-medium">Fetched</th>
            <th className="py-2 pr-3 text-right font-medium">Matched</th>
            <th className="py-2 pr-3 text-right font-medium">Age</th>
            <th className="py-2 pr-3 text-center font-medium">Freshness</th>
            <th className="py-2 text-right font-medium">Streak</th>
          </tr>
        </thead>
        <tbody>
          {sources.map((s, i) => (
            <tr
              key={`${s.connector}::${s.source_name}::${i}`}
              className={cn(
                "border-b border-border/40 transition-colors hover:bg-muted/20",
                !s.working && "opacity-70"
              )}
            >
              <td className="py-1.5 pr-3 max-w-[160px]">
                <div className="flex items-center gap-2">
                  {statusDot(s.working)}
                  <span className="truncate" title={s.source_name}>
                    {s.source_name}
                  </span>
                </div>
              </td>
              <td className="py-1.5 pr-3 text-muted-foreground">{s.connector}</td>
              <td className="py-1.5 pr-3 text-center">
                <Badge
                  variant={s.working ? "success" : "destructive"}
                  className="text-[10px] px-1.5 py-0"
                >
                  {s.working ? "ok" : "fail"}
                </Badge>
              </td>
              <td className="py-1.5 pr-3 text-right tabular-nums">{s.fetched_count}</td>
              <td className="py-1.5 pr-3 text-right tabular-nums">{s.matched_count}</td>
              <td className="py-1.5 pr-3 text-right tabular-nums text-muted-foreground">
                {s.latest_age_days !== null ? `${s.latest_age_days.toFixed(1)}d` : "—"}
              </td>
              <td className="py-1.5 pr-3 text-center">
                <Badge
                  variant={freshnessVariant(s.freshness_status)}
                  className="text-[10px] px-1.5 py-0"
                >
                  {s.freshness_status}
                </Badge>
              </td>
              <td className="py-1.5 text-right tabular-nums">
                {s.stale_streak > 0 ? (
                  <span className="text-warning">{s.stale_streak}×</span>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
