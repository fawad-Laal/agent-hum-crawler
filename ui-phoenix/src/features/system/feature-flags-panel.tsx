/**
 * FeatureFlagsPanel — interactive feature flag toggle list
 * Reads flags from overview response and sends PATCH via useUpdateFeatureFlag.
 * Each flag renders as a labelled Switch with pending/error feedback.
 */

import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { useUpdateFeatureFlag } from "@/hooks/use-mutations";
import { toast } from "sonner";
import { Flag } from "lucide-react";
import { cn } from "@/lib/utils";

interface FeatureFlagsPanelProps {
  flags: Record<string, boolean> | undefined;
  isLoading: boolean;
}

const FLAG_DESCRIPTIONS: Record<string, string> = {
  use_llm: "LLM enrichment for report generation",
  quality_gate: "Block low-quality source data from analysis",
  rust_accelerated: "Use Rust core for high-performance processing",
  dedup_aggressive: "Aggressive cross-source deduplication",
  cache_sources: "Cache source feeds between collection runs",
  debug_mode: "Verbose logging and diagnostic output",
};

function flagLabel(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function FeatureFlagsPanel({ flags, isLoading }: FeatureFlagsPanelProps) {
  const { mutate: toggle, isPending, variables } = useUpdateFeatureFlag();

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );
  }

  if (!flags || Object.keys(flags).length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No feature flags configured.
      </p>
    );
  }

  const sorted = Object.entries(flags).sort(([a], [b]) => a.localeCompare(b));

  return (
    <div className="space-y-1">
      {sorted.map(([flag, enabled]) => {
        const isThisPending = isPending && variables?.flag === flag;
        const description = FLAG_DESCRIPTIONS[flag];

        return (
          <div
            key={flag}
            className={cn(
              "flex items-center justify-between gap-4 rounded-lg px-3 py-2.5 transition-colors",
              "hover:bg-muted/30",
              isThisPending && "opacity-60 pointer-events-none"
            )}
          >
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <Flag
                  className={cn(
                    "h-3.5 w-3.5 flex-shrink-0",
                    enabled ? "text-primary" : "text-muted-foreground"
                  )}
                />
                <span className="text-sm font-medium">{flagLabel(flag)}</span>
              </div>
              {description && (
                <p className="text-xs text-muted-foreground pl-5.5 mt-0.5">
                  {description}
                </p>
              )}
            </div>

            <Switch
              checked={enabled}
              onCheckedChange={(next) => {
                toggle(
                  { flag, enabled: next },
                  {
                    onError: (err) => {
                      toast.error(`Failed to toggle ${flag}: ${err.message}`);
                    },
                    onSuccess: () => {
                      toast.success(
                        `${flagLabel(flag)} ${next ? "enabled" : "disabled"}`
                      );
                    },
                  }
                );
              }}
              aria-label={`Toggle ${flag}`}
              disabled={isThisPending}
            />
          </div>
        );
      })}
    </div>
  );
}
