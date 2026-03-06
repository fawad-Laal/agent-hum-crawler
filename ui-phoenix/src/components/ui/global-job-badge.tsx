/**
 * Project Phoenix — GlobalJobBadge (Phase 8 + 9.6)
 * Renders an animated badge when background jobs are queued or running.
 * Reads from the Zustand jobs store — no props needed for job tracking.
 * Shows operator-facing elapsed time (R18): "Label · 12s".
 * Returns null when no jobs are active so it's safe to always render.
 */

import { useEffect, useState } from "react";
import { useJobsStore } from "@/stores/jobs-store";
import { Badge } from "@/components/ui/badge";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export function GlobalJobBadge({ className }: { className?: string }) {
  const jobs = useJobsStore((s) => s.jobs);

  // Tick every second to keep elapsed display fresh (R18)
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((n) => n + 1), 1_000);
    return () => clearInterval(id);
  }, []);

  const active = Object.values(jobs).filter(
    (j) => j.status === "queued" || j.status === "running",
  );

  if (active.length === 0) return null;

  // Use the earliest startedAt for multi-job elapsed display
  const oldestStart = Math.min(...active.map((j) => j.startedAt));
  const elapsedSec = Math.round((Date.now() - oldestStart) / 1_000);

  const baseLabel =
    active.length === 1
      ? active[0].label
      : `${active.length} jobs running`;

  const label = `${baseLabel} · ${elapsedSec}s`;

  return (
    <Badge
      variant="secondary"
      className={cn(
        "flex animate-pulse items-center gap-1.5 text-xs font-medium",
        className,
      )}
    >
      <Loader2 className="h-3 w-3 animate-spin" />
      {label}
    </Badge>
  );
}
