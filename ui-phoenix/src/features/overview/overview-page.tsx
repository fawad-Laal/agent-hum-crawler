import { useOverview } from "@/hooks/use-queries";
import { KPICard, KPICardSkeleton } from "@/components/charts/kpi-card";
import { TrendChart } from "@/components/charts/trend-chart";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { fmtNumber, fmtPercent } from "@/lib/utils";
import {
  BarChart3,
  Activity,
  Copy,
  Link,
  ShieldCheck,
} from "lucide-react";

export function OverviewPage() {
  const { data: overview, isLoading, error } = useOverview();

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-20">
        <p className="text-destructive text-lg font-medium">Failed to load overview</p>
        <p className="text-sm text-muted-foreground">{error.message}</p>
      </div>
    );
  }

  const q = overview?.quality;
  const h = overview?.hardening;

  return (
    <div className="space-y-8">
      {/* KPI Cards */}
      <section>
        <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-muted-foreground">
          Key Metrics
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {isLoading ? (
            Array.from({ length: 5 }).map((_, i) => <KPICardSkeleton key={i} />)
          ) : (
            <>
              <KPICard
                label="Cycles"
                value={fmtNumber(q?.cycles_analyzed, 0)}
                icon={BarChart3}
                subtitle="Analyzed"
                tone="info"
              />
              <KPICard
                label="Events"
                value={fmtNumber(q?.events_analyzed, 0)}
                icon={Activity}
                subtitle="Total events"
                tone="info"
              />
              <KPICard
                label="Dup Rate"
                value={fmtPercent(q?.duplicate_rate_estimate)}
                icon={Copy}
                subtitle="Duplicate estimate"
                tone={
                  q && (q.duplicate_rate_estimate ?? 1) < 0.15 ? "pass" : "fail"
                }
              />
              <KPICard
                label="Traceable"
                value={fmtPercent(q?.traceable_rate)}
                icon={Link}
                subtitle="Source attribution"
                tone={
                  q && (q.traceable_rate ?? 0) > 0.8 ? "pass" : "fail"
                }
              />
              <KPICard
                label="Hardening"
                value={h?.status ?? "-"}
                icon={ShieldCheck}
                subtitle="Gate status"
                tone={h?.status === "pass" ? "pass" : "fail"}
              />
            </>
          )}
        </div>
      </section>

      {/* Trend Charts */}
      {overview && (
        <section>
          <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-muted-foreground">
            Trends
          </h2>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Cycle Trends */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Cycle Trends</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <TrendChart
                  label="Events per Cycle"
                  values={overview.cycles.map((c) => c.events ?? 0)}
                  color="#1591d4"
                />
                <TrendChart
                  label="LLM Enriched per Cycle"
                  values={overview.cycles.map((c) => c.llm_enriched ?? 0)}
                  color="#a855f7"
                />
              </CardContent>
            </Card>

            {/* Quality Trends */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Quality Rate Trends</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <TrendChart
                  label="Duplicate Rate"
                  values={overview.quality_trend.map((t) => t.duplicate_rate ?? t.duplicate_rate_estimate ?? 0)}
                  color="#ef4444"
                  yMax={1}
                />
                <TrendChart
                  label="Traceable Rate"
                  values={overview.quality_trend.map((t) => t.traceable_rate ?? 0)}
                  color="#1ec97e"
                  yMax={1}
                />
                <TrendChart
                  label="Citation Rate"
                  values={overview.quality_trend.map((t) => t.citation_rate ?? t.citation_coverage_rate ?? 0)}
                  color="#f59e0b"
                  yMax={1}
                />
              </CardContent>
            </Card>
          </div>
        </section>
      )}

      {/* Credibility Distribution */}
      {overview?.credibility_distribution && (
        <section>
          <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-muted-foreground">
            Source Credibility Distribution
          </h2>
          <Card className="p-5">
            <div className="flex items-end gap-6">
              {(
                Object.entries(overview.credibility_distribution) as [
                  string,
                  number,
                ][]
              ).map(([tier, count]) => (
                <div key={tier} className="flex flex-col items-center gap-1">
                  <span className="text-lg font-bold tabular-nums">{count}</span>
                  <Badge
                    variant={
                      tier === "high"
                        ? "success"
                        : tier === "medium"
                          ? "warning"
                          : tier === "low"
                            ? "destructive"
                            : "outline"
                    }
                  >
                    {tier}
                  </Badge>
                </div>
              ))}
            </div>
          </Card>
        </section>
      )}

      {/* Source Health Summary */}
      {overview?.source_health && (
        <section>
          <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-muted-foreground">
            Source Health
          </h2>
          <Card className="p-5">
            <div className="flex items-center gap-4">
              <Badge variant="success">
                {overview.source_health.working} working
              </Badge>
              <Badge variant="outline">
                {overview.source_health.total} total
              </Badge>
            </div>
            {(overview.source_health.top_failing?.length ?? 0) > 0 && (
              <div className="mt-4">
                <p className="mb-2 text-xs font-medium text-muted-foreground">
                  Top Failing Sources
                </p>
                <div className="space-y-1">
                  {(overview.source_health.top_failing ?? []).map((s) => (
                    <div
                      key={s.source_name}
                      className="flex items-center justify-between rounded-md bg-muted/30 px-3 py-1.5 text-sm"
                    >
                      <span className="text-destructive">{s.source_name}</span>
                      <span className="text-xs text-muted-foreground">
                        {s.connector} — streak {s.stale_streak}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Card>
        </section>
      )}
    </div>
  );
}
