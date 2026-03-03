/**
 * FreshnessTrendChart — Recharts line chart for source freshness
 * Plots latest_age_days for each source in a source-check result set,
 * sorted ascending (freshest first) to form a rising freshness curve.
 */

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  type TooltipProps,
} from "recharts";
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent";
import type { SourceCheckResult } from "@/types";

interface FreshnessTrendChartProps {
  sources: SourceCheckResult[];
  /** Days threshold above which a source is considered stale (default 7) */
  staleThreshold?: number;
}

interface ChartPoint {
  label: string;
  age_days: number | null;
  connector: string;
  status: string;
}

function CustomTooltip({ active, payload }: TooltipProps<ValueType, NameType>) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload as ChartPoint;
  return (
    <div className="rounded-md border border-border bg-popover px-3 py-2 shadow-md text-xs space-y-1">
      <p className="font-medium text-foreground truncate max-w-48">{p.label}</p>
      <p className="text-muted-foreground">Connector: {p.connector}</p>
      <p>
        Age:{" "}
        <span className={p.age_days !== null && p.age_days > 7 ? "text-destructive" : "text-status-pass"}>
          {p.age_days !== null ? `${p.age_days.toFixed(1)}d` : "n/a"}
        </span>
      </p>
      <p className="text-muted-foreground">Status: {p.status}</p>
    </div>
  );
}

export function FreshnessTrendChart({
  sources,
  staleThreshold = 7,
}: FreshnessTrendChartProps) {
  const data: ChartPoint[] = sources
    .filter((s) => s.latest_age_days !== null)
    .sort((a, b) => (a.latest_age_days ?? 999) - (b.latest_age_days ?? 999))
    .map((s) => ({
      label: s.source_name,
      age_days: s.latest_age_days,
      connector: s.connector,
      status: s.freshness_status,
    }));

  if (!data.length) {
    return (
      <p className="text-xs text-muted-foreground py-4 text-center">
        No freshness data available — run a source check first.
      </p>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart
        data={data}
        margin={{ top: 8, right: 16, left: 0, bottom: 4 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.5} />
        <XAxis
          dataKey="label"
          tick={false}
          axisLine={false}
          tickLine={false}
          label={{
            value: `${data.length} sources (sorted by age ↑)`,
            position: "insideBottom",
            offset: -2,
            className: "fill-muted-foreground text-xs",
            style: { fontSize: 11, fill: "var(--muted-foreground)" },
          }}
          height={32}
        />
        <YAxis
          tickCount={5}
          tickFormatter={(v: number) => `${v}d`}
          tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
          axisLine={false}
          tickLine={false}
          width={36}
        />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine
          y={staleThreshold}
          stroke="var(--destructive)"
          strokeDasharray="4 3"
          label={{
            value: `${staleThreshold}d stale`,
            position: "insideTopRight",
            style: { fontSize: 10, fill: "var(--destructive)" },
          }}
        />
        <Line
          type="monotone"
          dataKey="age_days"
          stroke="var(--primary)"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: "var(--primary)" }}
          name="Age (days)"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
