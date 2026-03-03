/**
 * TrendChart — Sparkline SVG component
 * Matches the original TinyLineChart from App.jsx
 */

import { useId } from "react";

interface TrendChartProps {
  values: number[];
  color?: string;
  yMax?: number | null;
  width?: number;
  height?: number;
  label?: string;
}

export function TrendChart({
  values,
  color = "#1ec97e",
  yMax = null,
  width = 260,
  height = 70,
  label,
}: TrendChartProps) {
  const gradientId = useId();
  if (!values.length) {
    return <div className="text-xs text-muted-foreground">No data</div>;
  }

  const max = yMax ?? Math.max(...values, 1);
  const min = 0;
  const stepX = values.length > 1 ? width / (values.length - 1) : width;
  const points = values
    .map((v, i) => {
      const x = i * stepX;
      const y = height - ((v - min) / (max - min || 1)) * height;
      return `${x},${y}`;
    })
    .join(" ");

  // Build gradient fill
  const fillPoints = `0,${height} ${points} ${width},${height}`;

  return (
    <div>
      {label && (
        <p className="mb-1 text-xs font-medium text-muted-foreground">{label}</p>
      )}
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className="overflow-visible"
      >
        {/* Gradient fill under the line */}
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.2" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        <polygon
          fill={`url(#${gradientId})`}
          points={fillPoints}
        />
        <polyline
          fill="none"
          stroke={color}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          points={points}
        />
        {/* End dot */}
        {values.length > 0 && (
          <circle
            cx={String((values.length - 1) * stepX)}
            cy={String(
              height - ((values[values.length - 1] - min) / (max - min || 1)) * height
            )}
            r="3"
            fill={color}
          />
        )}
      </svg>
    </div>
  );
}
