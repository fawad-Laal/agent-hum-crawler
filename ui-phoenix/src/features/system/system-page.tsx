import { useOverview } from "@/hooks/use-queries";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ShieldCheck, FlaskRound, Flag } from "lucide-react";
import { fmtDate } from "@/lib/utils";
import { FeatureFlagsPanel } from "@/features/system/feature-flags-panel";
import { SecurityBaselineCard } from "@/features/system/security-baseline-card";

export function SystemPage() {
  const { data: overview, isLoading } = useOverview();

  return (
    <div className="space-y-6">
      {/* E2E Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FlaskRound className="h-5 w-5 text-primary" />
            E2E Gate Summary
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : overview?.latest_e2e_summary ? (
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <Badge
                  variant={
                    overview.latest_e2e_summary.status === "pass"
                      ? "success"
                      : "destructive"
                  }
                >
                  {overview.latest_e2e_summary.status}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {fmtDate(overview.latest_e2e_summary.timestamp)}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {Object.entries(overview.latest_e2e_summary.steps).map(
                  ([step, status]) => (
                    <div
                      key={step}
                      className="flex items-center gap-2 rounded-md bg-muted/30 px-3 py-1.5 text-xs"
                    >
                      <span
                        className={
                          status === "pass"
                            ? "text-status-pass"
                            : "text-status-fail"
                        }
                        aria-label={`${step}: ${status}`}
                      >
                        ●
                      </span>
                      <span className="text-muted-foreground">{step}</span>
                    </div>
                  )
                )}
              </div>
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">
              No E2E gate runs found.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Hardening Status */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-primary" />
            Hardening Gate
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-12 w-full" />
          ) : (
            <Badge
              variant={
                overview?.hardening?.status === "pass"
                  ? "success"
                  : "destructive"
              }
            >
              {overview?.hardening?.status ?? "unknown"}
            </Badge>
          )}
        </CardContent>
      </Card>

      {/* Feature Flags */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Flag className="h-5 w-5 text-primary" />
            Feature Flags
          </CardTitle>
        </CardHeader>
        <CardContent>
          <FeatureFlagsPanel
            flags={overview?.feature_flags}
            isLoading={isLoading}
          />
        </CardContent>
      </Card>

      {/* Security Baseline */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-primary" />
            Security Baseline
          </CardTitle>
        </CardHeader>
        <CardContent>
          <SecurityBaselineCard
            hardening={overview?.hardening}
            e2eSummary={overview?.latest_e2e_summary}
            isLoading={isLoading}
          />
        </CardContent>
      </Card>
    </div>
  );
}
