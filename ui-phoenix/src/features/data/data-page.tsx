/**
 * DataPage — Database Explorer
 * Browse the raw contents of the monitoring database:
 * Cycle Runs · Events · Raw Items · Feed Health
 */

import { useState } from "react";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import {
  useDbCycles,
  useDbEvents,
  useDbRawItems,
  useDbFeedHealth,
} from "@/hooks/use-queries";
import type { DbCycleRun, DbEventRecord, DbRawItem, DbFeedHealthRecord } from "@/types";
import {
  Database,
  RefreshCw,
  Search,
  CheckCircle2,
  XCircle,
  Clock,
  FileText,
  Radio,
  Activity,
  Layers,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/lib/query-keys";

// ── Helpers ─────────────────────────────────────────────────

function fmt(val: string | null | undefined): string {
  if (!val) return "—";
  const d = new Date(val);
  if (isNaN(d.getTime())) return val;
  return d.toLocaleString();
}

function truncate(s: string, n = 80): string {
  if (!s) return "—";
  return s.length > n ? s.slice(0, n) + "…" : s;
}

function SeverityBadge({ severity }: { severity: string }) {
  const map: Record<string, "destructive" | "warning" | "secondary" | "outline"> = {
    critical: "destructive",
    high: "destructive",
    medium: "warning",
    low: "secondary",
  };
  return (
    <Badge variant={map[severity?.toLowerCase()] ?? "outline"} className="text-xs">
      {severity}
    </Badge>
  );
}

function StatusBadge({ status }: { status: string }) {
  const ok = status === "ok" || status === "success" || status === "new";
  return (
    <Badge variant={ok ? "secondary" : "destructive"} className="text-xs gap-1">
      {ok ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
      {status}
    </Badge>
  );
}

// ── Stats strip ──────────────────────────────────────────────

interface StatsStripProps {
  stats: { label: string; value: string | number }[];
}
function StatsStrip({ stats }: StatsStripProps) {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {stats.map((s) => (
        <div key={s.label} className="rounded-lg bg-muted/30 px-4 py-3 text-center">
          <p className="text-xl font-bold tabular-nums">{s.value}</p>
          <p className="text-xs text-muted-foreground mt-0.5">{s.label}</p>
        </div>
      ))}
    </div>
  );
}

// ── Cycles tab ───────────────────────────────────────────────

function CyclesTab() {
  const { data, isLoading, isError, refetch } = useDbCycles(50);
  const cycles = data?.cycles ?? [];

  if (isLoading) return <TableSkeleton rows={6} cols={6} />;
  if (isError) return <ErrorNote message="Could not load cycle runs from the database." />;

  const totalEvents = cycles.reduce((s, c) => s + (c.event_count ?? 0), 0);
  const totalRaw = cycles.reduce((s, c) => s + (c.raw_item_count ?? 0), 0);
  const llmEnabled = cycles.filter((c) => c.llm_enabled).length;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <StatsStrip stats={[
          { label: "Total Cycles shown", value: cycles.length },
          { label: "Total Events", value: totalEvents },
          { label: "Total Raw Items", value: totalRaw },
          { label: "LLM-enabled Cycles", value: llmEnabled },
        ]} />
        <Button variant="ghost" size="sm" onClick={() => refetch()} className="shrink-0 ml-2">
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/40">
            <tr>
              {["ID", "Run At", "Connectors", "Raw Items", "Events", "LLM"].map((h) => (
                <th key={h} className="px-3 py-2.5 text-left text-xs font-semibold text-muted-foreground whitespace-nowrap">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {cycles.map((c: DbCycleRun, i) => (
              <tr
                key={c.id}
                className={i % 2 === 0 ? "bg-card" : "bg-muted/10"}
              >
                <td className="px-3 py-2 font-mono text-xs text-muted-foreground">{c.id}</td>
                <td className="px-3 py-2 text-xs whitespace-nowrap">
                  <span className="flex items-center gap-1.5">
                    <Clock className="h-3 w-3 text-muted-foreground shrink-0" />
                    {fmt(c.run_at)}
                  </span>
                </td>
                <td className="px-3 py-2 tabular-nums text-center">{c.connector_count}</td>
                <td className="px-3 py-2 tabular-nums text-center">{c.raw_item_count}</td>
                <td className="px-3 py-2 tabular-nums text-center font-semibold">{c.event_count}</td>
                <td className="px-3 py-2 text-center">
                  {c.llm_enabled ? (
                    <Badge variant="secondary" className="text-xs">on</Badge>
                  ) : (
                    <Badge variant="outline" className="text-xs">off</Badge>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {cycles.length === 0 && (
          <p className="py-8 text-center text-sm text-muted-foreground">No cycle runs found.</p>
        )}
      </div>
    </div>
  );
}

// ── Events tab ───────────────────────────────────────────────

function EventsTab() {
  const [search, setSearch] = useState("");
  const [country, setCountry] = useState("");
  const { data, isLoading, isError, refetch } = useDbEvents({ limit: 200, country: country || undefined });
  const rawEvents = data?.events ?? [];

  const events = search
    ? rawEvents.filter(
        (e) =>
          e.title.toLowerCase().includes(search.toLowerCase()) ||
          e.country.toLowerCase().includes(search.toLowerCase()) ||
          e.disaster_type.toLowerCase().includes(search.toLowerCase()),
      )
    : rawEvents;

  const countries = [...new Set(rawEvents.map((e) => e.country))].sort();

  if (isLoading) return <TableSkeleton rows={8} cols={7} />;
  if (isError) return <ErrorNote message="Could not load events from the database." />;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[180px]">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            className="pl-8 h-8 text-sm"
            placeholder="Search title / country / type…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          className="h-8 rounded-md border border-input bg-background px-2.5 text-sm"
          value={country}
          onChange={(e) => setCountry(e.target.value)}
        >
          <option value="">All countries</option>
          {countries.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <Button variant="ghost" size="sm" onClick={() => refetch()}>
          <RefreshCw className="h-4 w-4" />
        </Button>
        <span className="text-xs text-muted-foreground ml-auto">
          {events.length} / {rawEvents.length} events
        </span>
      </div>

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/40">
            <tr>
              {["Title", "Country", "Type", "Severity", "Status", "LLM", "Published"].map((h) => (
                <th key={h} className="px-3 py-2.5 text-left text-xs font-semibold text-muted-foreground whitespace-nowrap">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {events.map((e: DbEventRecord, i) => (
              <tr key={e.id} className={i % 2 === 0 ? "bg-card" : "bg-muted/10"}>
                <td className="px-3 py-2 max-w-xs">
                  <a
                    href={e.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline text-xs"
                    title={e.title}
                  >
                    {truncate(e.title, 70)}
                  </a>
                </td>
                <td className="px-3 py-2 text-xs whitespace-nowrap">
                  <Badge variant="outline" className="text-xs">{e.country}</Badge>
                </td>
                <td className="px-3 py-2 text-xs text-muted-foreground whitespace-nowrap">
                  {truncate(e.disaster_type, 30)}
                </td>
                <td className="px-3 py-2">
                  <SeverityBadge severity={e.severity} />
                </td>
                <td className="px-3 py-2">
                  <StatusBadge status={e.status} />
                </td>
                <td className="px-3 py-2 text-center">
                  {e.llm_enriched ? (
                    <Badge variant="secondary" className="text-xs">✓</Badge>
                  ) : (
                    <span className="text-muted-foreground text-xs">—</span>
                  )}
                </td>
                <td className="px-3 py-2 text-xs text-muted-foreground whitespace-nowrap">
                  {fmt(e.published_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {events.length === 0 && (
          <p className="py-8 text-center text-sm text-muted-foreground">No events found.</p>
        )}
      </div>
    </div>
  );
}

// ── Raw Items tab ────────────────────────────────────────────

function RawItemsTab() {
  const [search, setSearch] = useState("");
  const { data, isLoading, isError, refetch } = useDbRawItems(200);
  const rawItems = data?.raw_items ?? [];

  const items = search
    ? rawItems.filter(
        (r) =>
          r.title.toLowerCase().includes(search.toLowerCase()) ||
          r.connector.toLowerCase().includes(search.toLowerCase()),
      )
    : rawItems;

  const byConnector = rawItems.reduce<Record<string, number>>((acc, r) => {
    acc[r.connector] = (acc[r.connector] ?? 0) + 1;
    return acc;
  }, {});

  if (isLoading) return <TableSkeleton rows={8} cols={5} />;
  if (isError) return <ErrorNote message="Could not load raw items from the database." />;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[180px]">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            className="pl-8 h-8 text-sm"
            placeholder="Search title / connector…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Button variant="ghost" size="sm" onClick={() => refetch()}>
          <RefreshCw className="h-4 w-4" />
        </Button>
        <span className="text-xs text-muted-foreground ml-auto">{items.length} items</span>
      </div>

      {/* Connector breakdown */}
      {Object.keys(byConnector).length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(byConnector).map(([k, v]) => (
            <Badge key={k} variant="secondary" className="text-xs gap-1">
              <Radio className="h-3 w-3" />
              {k}: {v}
            </Badge>
          ))}
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/40">
            <tr>
              {["Title", "Connector", "Type", "Published", "Cycle"].map((h) => (
                <th key={h} className="px-3 py-2.5 text-left text-xs font-semibold text-muted-foreground whitespace-nowrap">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((r: DbRawItem, i) => (
              <tr key={r.id} className={i % 2 === 0 ? "bg-card" : "bg-muted/10"}>
                <td className="px-3 py-2 max-w-xs">
                  {r.url ? (
                    <a
                      href={r.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline text-xs"
                      title={r.title}
                    >
                      {truncate(r.title, 70)}
                    </a>
                  ) : (
                    <span className="text-xs">{truncate(r.title, 70)}</span>
                  )}
                </td>
                <td className="px-3 py-2">
                  <Badge variant="outline" className="text-xs">{r.connector}</Badge>
                </td>
                <td className="px-3 py-2 text-xs text-muted-foreground">{r.source_type}</td>
                <td className="px-3 py-2 text-xs text-muted-foreground whitespace-nowrap">
                  {fmt(r.published_at)}
                </td>
                <td className="px-3 py-2 font-mono text-xs text-muted-foreground">{r.cycle_id}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {items.length === 0 && (
          <p className="py-8 text-center text-sm text-muted-foreground">No raw items found.</p>
        )}
      </div>
    </div>
  );
}

// ── Feed Health tab ──────────────────────────────────────────

function FeedHealthTab() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"" | "ok" | "error">("");
  const { data, isLoading, isError, refetch } = useDbFeedHealth(200);
  const records = data?.feed_health ?? [];

  const filtered = records.filter((r) => {
    if (statusFilter && r.status !== statusFilter) return false;
    if (search && !r.source_name.toLowerCase().includes(search.toLowerCase()) &&
        !r.connector.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const okCount = records.filter((r) => r.status === "ok").length;
  const errCount = records.filter((r) => r.status !== "ok").length;

  if (isLoading) return <TableSkeleton rows={8} cols={6} />;
  if (isError) return <ErrorNote message="Could not load feed health from the database." />;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[180px]">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            className="pl-8 h-8 text-sm"
            placeholder="Search source / connector…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          className="h-8 rounded-md border border-input bg-background px-2.5 text-sm"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as "" | "ok" | "error")}
        >
          <option value="">All statuses</option>
          <option value="ok">OK</option>
          <option value="error">Error</option>
        </select>
        <Button variant="ghost" size="sm" onClick={() => refetch()}>
          <RefreshCw className="h-4 w-4" />
        </Button>
        <div className="flex gap-1 ml-auto">
          <Badge variant="secondary" className="text-xs gap-1">
            <CheckCircle2 className="h-3 w-3 text-green-500" />{okCount} ok
          </Badge>
          <Badge variant="destructive" className="text-xs gap-1">
            <XCircle className="h-3 w-3" />{errCount} errors
          </Badge>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/40">
            <tr>
              {["Source", "Connector", "Status", "Fetched", "Matched", "Cycle", "Error"].map((h) => (
                <th key={h} className="px-3 py-2.5 text-left text-xs font-semibold text-muted-foreground whitespace-nowrap">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((r: DbFeedHealthRecord, i) => (
              <tr key={r.id} className={i % 2 === 0 ? "bg-card" : "bg-muted/10"}>
                <td className="px-3 py-2 max-w-xs">
                  {r.source_url ? (
                    <a
                      href={r.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline text-xs"
                      title={r.source_name}
                    >
                      {truncate(r.source_name, 50)}
                    </a>
                  ) : (
                    <span className="text-xs">{truncate(r.source_name, 50)}</span>
                  )}
                </td>
                <td className="px-3 py-2">
                  <Badge variant="outline" className="text-xs">{r.connector}</Badge>
                </td>
                <td className="px-3 py-2">
                  <StatusBadge status={r.status} />
                </td>
                <td className="px-3 py-2 tabular-nums text-center text-xs">{r.fetched_count ?? 0}</td>
                <td className="px-3 py-2 tabular-nums text-center text-xs">{r.matched_count ?? 0}</td>
                <td className="px-3 py-2 font-mono text-xs text-muted-foreground">{r.cycle_id}</td>
                <td className="px-3 py-2 max-w-[180px]">
                  {r.error ? (
                    <span className="text-xs text-destructive" title={r.error}>
                      {truncate(r.error, 60)}
                    </span>
                  ) : (
                    <span className="text-xs text-muted-foreground">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <p className="py-8 text-center text-sm text-muted-foreground">No records found.</p>
        )}
      </div>
    </div>
  );
}

// ── Utility components ───────────────────────────────────────

function TableSkeleton({ rows, cols }: { rows: number; cols: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-2">
          {Array.from({ length: cols }).map((_, j) => (
            <Skeleton key={j} className="h-8 flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
}

function ErrorNote({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive flex items-center gap-2">
      <XCircle className="h-4 w-4 shrink-0" />
      {message}
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────

export function DataPage() {
  const qc = useQueryClient();

  function refreshAll() {
    qc.invalidateQueries({ queryKey: ["db"] });
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Database className="h-6 w-6 text-primary" />
            Database Explorer
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Browse all records stored in the monitoring database by the collection pipeline.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={refreshAll} className="shrink-0">
          <RefreshCw className="h-4 w-4 mr-1.5" />
          Refresh all
        </Button>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="events">
        <TabsList className="mb-4">
          <TabsTrigger value="cycles" className="gap-1.5">
            <Activity className="h-3.5 w-3.5" />
            Cycle Runs
          </TabsTrigger>
          <TabsTrigger value="events" className="gap-1.5">
            <Layers className="h-3.5 w-3.5" />
            Events
          </TabsTrigger>
          <TabsTrigger value="raw" className="gap-1.5">
            <FileText className="h-3.5 w-3.5" />
            Raw Items
          </TabsTrigger>
          <TabsTrigger value="feed-health" className="gap-1.5">
            <Radio className="h-3.5 w-3.5" />
            Feed Health
          </TabsTrigger>
        </TabsList>

        <TabsContent value="cycles">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Cycle Runs</CardTitle>
              <CardDescription>
                Each row is one execution of <code className="text-xs">run-cycle</code>.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <CyclesTab />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="events">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Processed Events</CardTitle>
              <CardDescription>
                Deduplicated, classified events extracted from raw source items.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <EventsTab />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="raw">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Raw Source Items</CardTitle>
              <CardDescription>
                Every article / feed item fetched before deduplication and classification.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <RawItemsTab />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="feed-health">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Feed Health</CardTitle>
              <CardDescription>
                Per-source fetch status for each cycle run.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <FeedHealthTab />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
