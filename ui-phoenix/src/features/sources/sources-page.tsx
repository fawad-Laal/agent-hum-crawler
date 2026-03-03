/**
 * SourcesPage — Phase 5
 * Source health table, connector diagnostics, freshness trend chart.
 * Data flows from useOverview (summary) + useRunSourceCheck (detailed check).
 */

import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { useOverview, useCountrySources } from "@/hooks/use-queries";
import { useRunSourceCheck } from "@/hooks/use-mutations";
import { useFormStore } from "@/stores/form-store";
import { SourceHealthTable } from "@/features/sources/source-health-table";
import { ConnectorDiagnostics } from "@/features/sources/connector-diagnostics";
import { FreshnessTrendChart } from "@/components/charts/freshness-trend-chart";
import type { SourceCheckResult } from "@/types";
import {
  Satellite,
  RefreshCw,
  Activity,
  Plug,
  TrendingUp,
  AlertTriangle,
} from "lucide-react";
import { toast } from "sonner";

// ── Overview-level source health summary ───────────────────

function OverviewSummary() {
  const { data: overview, isLoading } = useOverview();

  if (isLoading) return <Skeleton className="h-20 w-full" />;

  const sh = overview?.source_health;
  if (!sh) return null;

  const healthPct = sh.total > 0 ? Math.round((sh.working / sh.total) * 100) : 0;
  const variant: "success" | "warning" | "destructive" =
    healthPct === 100 ? "success" : healthPct >= 70 ? "warning" : "destructive";

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-lg bg-muted/30 px-4 py-3 text-center">
          <p className="text-2xl font-bold tabular-nums">{sh.working}</p>
          <p className="text-xs text-muted-foreground">Working</p>
        </div>
        <div className="rounded-lg bg-muted/30 px-4 py-3 text-center">
          <p className="text-2xl font-bold tabular-nums">{sh.total - sh.working}</p>
          <p className="text-xs text-muted-foreground">Failing</p>
        </div>
        <div className="rounded-lg bg-muted/30 px-4 py-3 text-center">
          <p className="text-2xl font-bold tabular-nums">
            <Badge variant={variant}>{healthPct}%</Badge>
          </p>
          <p className="text-xs text-muted-foreground mt-1">Health</p>
        </div>
      </div>

      {sh.top_failing.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-medium text-muted-foreground flex items-center gap-1">
            <AlertTriangle className="h-3.5 w-3.5 text-warning" />
            Top failing sources
          </p>
          {sh.top_failing.map((f) => (
            <div
              key={`${f.connector}::${f.source_name}`}
              className="flex items-center justify-between rounded-md bg-muted/20 px-3 py-1.5 text-xs"
            >
              <span className="truncate text-muted-foreground">
                <span className="text-foreground font-medium">{f.source_name}</span>
                {" "}({f.connector})
              </span>
              <span className="ml-2 flex-shrink-0 text-warning">
                {f.stale_streak}× stale
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Tabbed results section ─────────────────────────────────

function ResultsSection({ results }: { results: SourceCheckResult[] }) {
  const working = results.filter((r) => r.working).length;
  const total = results.length;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base">
            <Activity className="h-4 w-4 text-primary" />
            Source Check Results
          </CardTitle>
          <Badge variant={working === total ? "success" : "warning"}>
            {working}/{total} working
          </Badge>
        </div>
        <CardDescription>
          {total} sources across {new Set(results.map((r) => r.connector)).size} connectors
        </CardDescription>
      </CardHeader>

      <CardContent>
        <Tabs defaultValue="table">
          <TabsList className="mb-4">
            <TabsTrigger value="table">Table</TabsTrigger>
            <TabsTrigger value="connectors">Connectors</TabsTrigger>
            <TabsTrigger value="trend">Freshness Trend</TabsTrigger>
          </TabsList>
          <TabsContent value="table">
            <SourceHealthTable sources={results} />
          </TabsContent>
          <TabsContent value="connectors">
            <ConnectorDiagnostics sources={results} />
          </TabsContent>
          <TabsContent value="trend">
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">
                Sources sorted freshest → stalest. Dashed line = 7-day stale threshold.
              </p>
              <FreshnessTrendChart sources={results} />
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}

// ── Country feeds summary ──────────────────────────────────

function CountryFeedsSummary() {
  const { data, isLoading } = useCountrySources();

  if (isLoading) return <Skeleton className="h-32 w-full" />;
  if (!data) return <p className="text-sm text-muted-foreground">No feed data.</p>;

  const sorted = [...data.countries].sort((a, b) => b.feed_count - a.feed_count);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-4 text-sm">
        <span>
          <span className="font-bold tabular-nums">{data.countries.length}</span>{" "}
          <span className="text-muted-foreground">countries</span>
        </span>
        <span>
          <span className="font-bold tabular-nums">{data.global_feed_count}</span>{" "}
          <span className="text-muted-foreground">global feeds</span>
        </span>
        <span>
          <span className="font-bold tabular-nums">
            {Object.keys(data.global_sources).length}
          </span>{" "}
          <span className="text-muted-foreground">connectors</span>
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
        {sorted.slice(0, 16).map((c) => (
          <div
            key={c.country}
            className="flex items-center justify-between rounded-md bg-muted/20 px-3 py-1.5 text-xs"
          >
            <span className="font-medium truncate">{c.country}</span>
            <Badge variant="outline" className="ml-1 text-[10px] px-1.5 py-0">
              {c.feed_count}
            </Badge>
          </div>
        ))}
        {sorted.length > 16 && (
          <div className="flex items-center justify-center rounded-md bg-muted/10 px-3 py-1.5 text-xs text-muted-foreground">
            +{sorted.length - 16} more
          </div>
        )}
      </div>

      <div>
        <p className="text-xs font-medium text-muted-foreground mb-1.5 flex items-center gap-1">
          <TrendingUp className="h-3.5 w-3.5" />
          Global connector breakdown
        </p>
        <div className="flex flex-wrap gap-2">
          {Object.entries(data.global_sources).map(([connector, srcs]) => (
            <Badge key={connector} variant="secondary">
              {connector}: {srcs.length}
            </Badge>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Main page ───────────────────────────────────────────────

export function SourcesPage() {
  const form = useFormStore((s) => s.form);
  const { mutate: runCheck, isPending, data: checkData } = useRunSourceCheck();

  const handleRunCheck = () => {
    runCheck(
      {
        countries: form.countries,
        disaster_types: form.disaster_types,
        limit: form.limit,
        max_age_days: form.max_age_days,
      },
      {
        onError: (err) => toast.error(`Source check failed: ${err.message}`),
        onSuccess: (data) =>
          toast.success(
            `Check complete — ${data.working_sources}/${data.total_sources} sources working`
          ),
      }
    );
  };

  return (
    <div className="space-y-6">
      {/* Header + overview summary */}
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-4">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Satellite className="h-5 w-5 text-primary" />
                Source Intelligence
              </CardTitle>
              <CardDescription className="mt-1">
                Live health status of all configured data source feeds.
              </CardDescription>
            </div>
            <Button
              onClick={handleRunCheck}
              disabled={isPending}
              size="sm"
              className="flex-shrink-0"
            >
              {isPending ? (
                <>
                  <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                  Checking…
                </>
              ) : (
                <>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Run Source Check
                </>
              )}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <OverviewSummary />
        </CardContent>
      </Card>

      {/* Detailed results — visible after a check runs */}
      {checkData && checkData.source_checks.length > 0 && (
        <ResultsSection results={checkData.source_checks} />
      )}

      {/* Feed config summary */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Plug className="h-4 w-4 text-primary" />
            Active Feed Configuration
          </CardTitle>
          <CardDescription>
            Feeds loaded from{" "}
            <code className="text-xs">config/country_sources.json</code>
          </CardDescription>
        </CardHeader>
        <CardContent>
          <CountryFeedsSummary />
        </CardContent>
      </Card>
    </div>
  );
}
