/**
 * Project Phoenix — GlobalJobBadge (Phase 8)
 * Renders an animated badge when background jobs are queued or running.
 * Reads from the Zustand jobs store — no props needed for job tracking.
 * Returns null when no jobs are active so it's safe to always render.
 */

import { useJobsStore } from "@/stores/jobs-store";
import { Badge } from "@/components/ui/badge";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export function GlobalJobBadge({ className }: { className?: string }) {
  const jobs = useJobsStore((s) => s.jobs);

  const active = Object.values(jobs).filter(
    (j) => j.status === "queued" || j.status === "running",
  );

  if (active.length === 0) return null;

  const label =
    active.length === 1
      ? active[0].label
      : `${active.length} jobs running`;

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
