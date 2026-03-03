/**
 * ConnectorDiagnostics — collapsible per-connector cards
 * Groups source check results by connector and renders each group
 * as an expandable card showing individual source rows.
 */

import { Collapsible } from "@/components/ui/collapsible";
import { Badge } from "@/components/ui/badge";
import type { SourceCheckResult } from "@/types";
import { cn } from "@/lib/utils";
import { Plug, AlertCircle, CheckCircle2 } from "lucide-react";

interface ConnectorDiagnosticsProps {
  sources: SourceCheckResult[];
}

interface ConnectorGroup {
  connector: string;
  sources: SourceCheckResult[];
  working: number;
  total: number;
}

function groupByConnector(sources: SourceCheckResult[]): ConnectorGroup[] {
  const map = new Map<string, SourceCheckResult[]>();
  for (const s of sources) {
    const arr = map.get(s.connector) ?? [];
    arr.push(s);
    map.set(s.connector, arr);
  }
  return Array.from(map.entries())
    .map(([connector, srcs]) => ({
      connector,
      sources: srcs,
      working: srcs.filter((s) => s.working).length,
      total: srcs.length,
    }))
    .sort((a, b) => a.working / a.total - b.working / b.total); // unhealthiest first
}

function SourceRow({ s }: { s: SourceCheckResult }) {
  const ok = s.working;
  return (
    <div
      className={cn(
        "rounded-md border border-border/50 px-3 py-2 text-xs space-y-1",
        !ok && "border-destructive/30 bg-destructive/5"
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          {ok ? (
            <CheckCircle2 className="h-3.5 w-3.5 flex-shrink-0 text-status-pass" />
          ) : (
            <AlertCircle className="h-3.5 w-3.5 flex-shrink-0 text-status-fail" />
          )}
          <span className="truncate font-medium" title={s.source_name}>
            {s.source_name}
          </span>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <Badge
            variant={
              s.freshness_status === "fresh"
                ? "success"
                : s.freshness_status === "aging"
                ? "warning"
                : "destructive"
            }
            className="text-[10px] px-1.5 py-0"
          >
            {s.freshness_status}
          </Badge>
          {s.stale_streak > 0 && (
            <span className="text-warning text-[10px]">{s.stale_streak}× stale</span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-x-4 text-muted-foreground">
        <span>Fetched: {s.fetched_count}</span>
        <span>Matched: {s.matched_count}</span>
        <span>
          Age:{" "}
          {s.latest_age_days !== null ? (
            <span
              className={
                s.latest_age_days > 7 ? "text-destructive" : "text-status-pass"
              }
            >
              {s.latest_age_days.toFixed(1)}d
            </span>
          ) : (
            "—"
          )}
        </span>
      </div>

      {!ok && s.error && (
        <p className="text-destructive/80 break-all leading-tight">{s.error}</p>
      )}

      {s.stale_action && (
        <p className="text-muted-foreground italic">Action: {s.stale_action}</p>
      )}
    </div>
  );
}

export function ConnectorDiagnostics({ sources }: ConnectorDiagnosticsProps) {
  const groups = groupByConnector(sources);

  if (!groups.length) {
    return (
      <p className="text-sm text-muted-foreground py-4 text-center">
        No connector data available.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {groups.map((group) => {
        const healthPct = Math.round((group.working / group.total) * 100);
        const isHealthy = group.working === group.total;
        const hasFailing = group.working < group.total;

        return (
          <Collapsible
            key={group.connector}
            defaultOpen={hasFailing}
            trigger={
              <div className="flex items-center gap-3 min-w-0 flex-1">
                <Plug
                  className={cn(
                    "h-4 w-4 flex-shrink-0",
                    isHealthy ? "text-status-pass" : "text-status-fail"
                  )}
                />
                <span className="font-medium truncate">{group.connector}</span>
                <Badge
                  variant={isHealthy ? "success" : hasFailing ? "destructive" : "warning"}
                  className="ml-auto text-[10px] px-1.5 py-0"
                >
                  {group.working}/{group.total} · {healthPct}%
                </Badge>
              </div>
            }
            className="rounded-lg border border-border bg-card/50"
          >
            <div className="space-y-2 pt-1 pb-2">
              {group.sources.map((s, i) => (
                <SourceRow key={`${s.source_name}::${i}`} s={s} />
              ))}
            </div>
          </Collapsible>
        );
      })}
    </div>
  );
}
