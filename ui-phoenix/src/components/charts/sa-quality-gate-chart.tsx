/**
 * SAQualityGateChart — Horizontal BarChart for 6-dimension SA quality gate
 * Each bar represents a scorer dimension (0–100%). Reference line at threshold.
 * Bar color: green ≥ 70%, yellow 50–69%, red < 50%.
 */

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  Cell,
  ResponsiveContainer,
  type TooltipProps,
} from "recharts";
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent";
import type { SAQualityGate } from "@/types";

interface SAQualityGateChartProps {
  qualityGate: SAQualityGate;
  /** Threshold percentage (0–100) for the reference line — default 70 */
  threshold?: number;
}

interface DimPoint {
  label: string;
  pct: number;
  key: string;
}

const DIM_CONFIG = [
  { key: "section_completeness", label: "Sections" },
  { key: "key_figure_coverage", label: "Key Figures" },
  { key: "citation_accuracy", label: "Citations" },
  { key: "citation_density", label: "Cit. Density" },
  { key: "admin_coverage", label: "Admin Areas" },
  { key: "date_attribution", label: "Dates" },
] as const;

function barColor(pct: number): string {
  if (pct >= 70) return "var(--color-status-pass, #22c55e)";
  if (pct >= 50) return "var(--color-warning, #f59e0b)";
  return "var(--color-status-fail, #ef4444)";
}

function CustomTooltip({ active, payload }: TooltipProps<ValueType, NameType>) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload as DimPoint;
  return (
    <div className="rounded-md border border-border bg-popover px-3 py-2 text-xs shadow-md">
      <p className="font-medium text-foreground">{d.label}</p>
      <p className="text-muted-foreground mt-0.5">{d.pct.toFixed(1)}%</p>
    </div>
  );
}

export function SAQualityGateChart({ qualityGate, threshold = 70 }: SAQualityGateChartProps) {
  const data: DimPoint[] = DIM_CONFIG.map(({ key, label }) => ({
    key,
    label,
    pct: ((qualityGate[key as keyof SAQualityGate] as number | undefined) ?? 0) * 100,
  }));

  const overallPct = (qualityGate.overall_score ?? 0) * 100;

  return (
    <div className="space-y-3">
      {/* Overall score summary */}
      <div className="flex items-center gap-3">
        <div className="flex-1 text-sm">
          <span className="text-muted-foreground">Overall score · </span>
          <span className="font-semibold tabular-nums" style={{ color: barColor(overallPct) }}>
            {overallPct.toFixed(1)}%
          </span>
        </div>
        <div
          className="rounded-full px-2.5 py-0.5 text-xs font-semibold"
          style={{
            background: qualityGate.passed
              ? "color-mix(in srgb, var(--color-status-pass, #22c55e) 15%, transparent)"
              : "color-mix(in srgb, var(--color-status-fail, #ef4444) 15%, transparent)",
            color: qualityGate.passed
              ? "var(--color-status-pass, #22c55e)"
              : "var(--color-status-fail, #ef4444)",
          }}
        >
          {qualityGate.passed ? "PASS" : "FAIL"}
        </div>
      </div>

      {/* Horizontal bar chart */}
      <ResponsiveContainer width="100%" height={220}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 0, right: 40, left: 8, bottom: 0 }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            horizontal={false}
            stroke="var(--color-border, #334155)"
          />
          <XAxis
            type="number"
            domain={[0, 100]}
            tickCount={6}
            tickFormatter={(v) => `${v}%`}
            tick={{ fontSize: 10, fill: "var(--color-muted-foreground, #94a3b8)" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={82}
            tick={{ fontSize: 10, fill: "var(--color-muted-foreground, #94a3b8)" }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(148,163,184,0.08)" }} />
          <ReferenceLine
            x={threshold}
            stroke="var(--color-muted-foreground, #94a3b8)"
            strokeDasharray="4 3"
            label={{
              value: `${threshold}%`,
              position: "top",
              fontSize: 9,
              fill: "var(--color-muted-foreground, #94a3b8)",
            }}
          />
          <Bar dataKey="pct" radius={[0, 3, 3, 0]} maxBarSize={18}>
            {data.map((entry) => (
              <Cell key={entry.key} fill={barColor(entry.pct)} fillOpacity={0.85} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
