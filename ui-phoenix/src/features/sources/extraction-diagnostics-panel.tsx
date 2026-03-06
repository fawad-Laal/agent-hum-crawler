import { useState } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  ReferenceLine,
} from "recharts";
import { AlertTriangle, ChevronDown, ChevronRight, Microscope } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useExtractionDiagnostics } from "@/hooks/use-queries";
import type { ExtractionConnectorStat, ExtractionMethodStat, ExtractionError } from "@/types";

// ── helpers ──────────────────────────────────────────────────────────────────

function okRateColor(rate: number): string {
  if (rate >= 0.8) return "#22c55e"; // green-500
  if (rate >= 0.5) return "#f59e0b"; // amber-500
  return "#ef4444"; // red-500
}

function pct(rate: number) {
  return `${Math.round(rate * 100)}%`;
}

// ── sub-components ────────────────────────────────────────────────────────────

function KpiCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border bg-card px-4 py-3 min-w-0">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-2xl font-semibold tabular-nums">{value}</span>
    </div>
  );
}

function LowYieldBadges({ connectors }: { connectors: string[] }) {
  if (!connectors.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3">
      <AlertTriangle className="h-4 w-4 shrink-0 text-amber-500" />
      <span className="text-sm font-medium text-amber-600 dark:text-amber-400">
        Low-yield connectors:
      </span>
      {connectors.map((c) => (
        <Badge key={c} variant="outline" className="border-amber-500/50 text-amber-600 dark:text-amber-400">
          {c}
        </Badge>
      ))}
    </div>
  );
}

function ConnectorChart({ rows }: { rows: ExtractionConnectorStat[] }) {
  const sorted = [...rows].sort((a, b) => a.ok_rate - b.ok_rate);
  return (
    <div>
      <h4 className="mb-3 text-sm font-medium text-muted-foreground">
        Connector OK-rate (last 20 cycles)
      </h4>
      <ResponsiveContainer width="100%" height={Math.max(120, sorted.length * 36)}>
        <BarChart
          data={sorted}
          layout="vertical"
          margin={{ top: 0, right: 40, left: 0, bottom: 0 }}
        >
          <XAxis
            type="number"
            domain={[0, 1]}
            tickFormatter={pct}
            tick={{ fontSize: 11 }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            type="category"
            dataKey="connector"
            width={130}
            tick={{ fontSize: 11 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            formatter={(v: number, _name: string, props: { payload?: ExtractionConnectorStat }) => [
              pct(v),
              `OK rate (${props.payload?.ok ?? 0}/${props.payload?.total ?? 0})`,
            ]}
            contentStyle={{ fontSize: 12 }}
          />
          <ReferenceLine x={0.8} stroke="#22c55e" strokeDasharray="3 3" strokeWidth={1} />
          <ReferenceLine x={0.5} stroke="#f59e0b" strokeDasharray="3 3" strokeWidth={1} />
          <Bar dataKey="ok_rate" radius={[0, 3, 3, 0]} maxBarSize={20}>
            {sorted.map((entry, i) => (
              <Cell key={i} fill={okRateColor(entry.ok_rate)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function MethodTable({ rows }: { rows: ExtractionMethodStat[] }) {
  return (
    <div>
      <h4 className="mb-3 text-sm font-medium text-muted-foreground">Extraction method breakdown</h4>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-muted-foreground text-xs">
              <th className="py-1.5 text-left font-medium">Method</th>
              <th className="py-1.5 text-right font-medium w-16">Total</th>
              <th className="py-1.5 text-right font-medium w-16">OK</th>
              <th className="py-1.5 text-right font-medium w-16">Failed</th>
              <th className="py-1.5 text-left font-medium pl-4 min-w-[120px]">OK rate</th>
              <th className="py-1.5 text-right font-medium w-24">Avg chars</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.method} className="border-b last:border-0 hover:bg-muted/30">
                <td className="py-1.5 font-mono text-xs">{r.method}</td>
                <td className="py-1.5 text-right tabular-nums">{r.total}</td>
                <td className="py-1.5 text-right tabular-nums text-green-600">{r.ok}</td>
                <td className="py-1.5 text-right tabular-nums text-red-500">{r.failed}</td>
                <td className="py-1.5 pl-4">
                  <div className="flex items-center gap-2">
                    <div className="relative h-2 w-24 rounded-full bg-muted overflow-hidden">
                      <div
                        className="absolute inset-y-0 left-0 rounded-full"
                        style={{
                          width: pct(r.ok_rate),
                          backgroundColor: okRateColor(r.ok_rate),
                        }}
                      />
                    </div>
                    <span className="text-xs tabular-nums" style={{ color: okRateColor(r.ok_rate) }}>
                      {pct(r.ok_rate)}
                    </span>
                  </div>
                </td>
                <td className="py-1.5 text-right tabular-nums text-muted-foreground">
                  {r.avg_char_count.toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TopErrorsList({ errors }: { errors: ExtractionError[] }) {
  const [open, setOpen] = useState(false);
  if (!errors.length) return null;
  return (
    <div>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
      >
        {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        Top errors ({errors.length})
      </button>
      {open && (
        <ul className="mt-2 space-y-1.5">
          {errors.map((e, i) => (
            <li
              key={i}
              className="flex items-start justify-between gap-4 rounded-md border bg-destructive/5 px-3 py-2 text-xs"
            >
              <div className="min-w-0">
                <span className="font-mono text-muted-foreground">{e.connector}</span>
                <span className="mx-1.5 text-muted-foreground/60">·</span>
                <span className="font-mono text-muted-foreground">{e.method}</span>
                <p className="mt-0.5 truncate text-destructive">{e.error}</p>
              </div>
              <Badge variant="destructive" className="shrink-0 tabular-nums">
                ×{e.count}
              </Badge>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function PanelSkeleton() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-16 rounded-lg" />
        ))}
      </div>
      <Skeleton className="h-40 rounded-lg" />
      <Skeleton className="h-32 rounded-lg" />
    </div>
  );
}

// ── main component ────────────────────────────────────────────────────────────

export function ExtractionDiagnosticsPanel() {
  const { data, isLoading, isError } = useExtractionDiagnostics({ limit_cycles: 20 });

  if (isLoading) return <PanelSkeleton />;

  if (isError || !data) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
        <AlertTriangle className="h-4 w-4 shrink-0" />
        Failed to load extraction diagnostics. Is the dashboard API running?
      </div>
    );
  }

  const totalDocs = data.total_records;
  const okCount = data.by_status["ok"] ?? 0;
  const overallOkRate = totalDocs > 0 ? okCount / totalDocs : 0;

  return (
    <div className="space-y-5">
      {/* KPI row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <KpiCard label="Total records" value={totalDocs.toLocaleString()} />
        <KpiCard label="Cycles analysed" value={data.cycles_analyzed} />
        <KpiCard
          label="Overall OK rate"
          value={pct(overallOkRate)}
        />
      </div>

      {/* Low yield warning */}
      <LowYieldBadges connectors={data.low_yield_connectors} />

      {/* Connector chart */}
      {data.by_connector.length > 0 && <ConnectorChart rows={data.by_connector} />}

      {/* Method table */}
      {data.by_method.length > 0 && <MethodTable rows={data.by_method} />}

      {/* Top errors */}
      <TopErrorsList errors={data.top_errors} />

      {/* Refresh hint */}
      <p className="text-xs text-muted-foreground/60">
        Showing last 20 cycles · data refreshes every 30 s
      </p>
    </div>
  );
}

// Header sub-component used by sources-page.tsx to avoid duplication
export function ExtractionDiagnosticsPanelHeader() {
  return (
    <div className="flex items-center gap-2">
      <Microscope className="h-5 w-5 text-muted-foreground" />
      <span>Extraction Diagnostics</span>
    </div>
  );
}
