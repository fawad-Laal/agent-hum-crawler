/**
 * SecurityBaselineCard — aggregates security posture from hardening gate,
 * E2E security_status, and hardening check details into a single status card.
 */

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import type { HardeningStatus, E2ESummary } from "@/types";
import { ShieldCheck, ShieldAlert, ShieldOff, CheckCircle2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { fmtDate } from "@/lib/utils";

interface SecurityBaselineCardProps {
  hardening: HardeningStatus | undefined;
  e2eSummary: E2ESummary | null | undefined;
  isLoading: boolean;
}

type SecurityLevel = "pass" | "warn" | "fail" | "unknown";

function deriveLevel(
  hardening: HardeningStatus | undefined,
  e2eSummary: E2ESummary | null | undefined
): SecurityLevel {
  if (!hardening) return "unknown";
  if (hardening.status === "fail") return "fail";
  if (e2eSummary?.security_status === "fail") return "warn";
  if (hardening.status === "pass") return "pass";
  return "unknown";
}

const levelConfig: Record<
  SecurityLevel,
  {
    icon: React.ReactNode;
    label: string;
    variant: "success" | "warning" | "destructive" | "secondary";
    color: string;
  }
> = {
  pass: {
    icon: <ShieldCheck className="h-10 w-10" />,
    label: "Baseline Secure",
    variant: "success",
    color: "text-status-pass",
  },
  warn: {
    icon: <ShieldAlert className="h-10 w-10" />,
    label: "Partial Compliance",
    variant: "warning",
    color: "text-warning",
  },
  fail: {
    icon: <ShieldOff className="h-10 w-10" />,
    label: "Baseline Failing",
    variant: "destructive",
    color: "text-status-fail",
  },
  unknown: {
    icon: <ShieldOff className="h-10 w-10" />,
    label: "Status Unknown",
    variant: "secondary",
    color: "text-muted-foreground",
  },
};

export function SecurityBaselineCard({
  hardening,
  e2eSummary,
  isLoading,
}: SecurityBaselineCardProps) {
  if (isLoading) {
    return <Skeleton className="h-36 w-full" />;
  }

  const level = deriveLevel(hardening, e2eSummary);
  const cfg = levelConfig[level];
  const checks = hardening?.checks ?? {};
  const checkEntries = Object.entries(checks);

  return (
    <div className="space-y-4">
      {/* Summary row */}
      <div className="flex items-center gap-4">
        <span className={cn("flex-shrink-0", cfg.color)}>{cfg.icon}</span>
        <div>
          <div className="flex items-center gap-2">
            <span className="font-semibold text-base">{cfg.label}</span>
            <Badge variant={cfg.variant}>{level}</Badge>
          </div>
          {e2eSummary && (
            <p className="text-xs text-muted-foreground mt-0.5">
              Last E2E run: {fmtDate(e2eSummary.timestamp)}
              {e2eSummary.security_status && (
                <> · Security gate:{" "}
                  <span
                    className={
                      e2eSummary.security_status === "pass"
                        ? "text-status-pass"
                        : "text-status-fail"
                    }
                  >
                    {e2eSummary.security_status}
                  </span>
                </>
              )}
            </p>
          )}
        </div>
      </div>

      {/* Hardening checks grid */}
      {checkEntries.length > 0 && (
        <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-3">
          {checkEntries.map(([check, passed]) => (
            <div
              key={check}
              className={cn(
                "flex items-center gap-2 rounded-md px-2.5 py-1.5 text-xs",
                passed ? "bg-status-pass/10" : "bg-status-fail/10"
              )}
            >
              {passed ? (
                <CheckCircle2 className="h-3.5 w-3.5 flex-shrink-0 text-status-pass" />
              ) : (
                <XCircle className="h-3.5 w-3.5 flex-shrink-0 text-status-fail" />
              )}
              <span className="truncate" title={check}>
                {check.replace(/_/g, " ")}
              </span>
            </div>
          ))}
        </div>
      )}

      {checkEntries.length === 0 && (
        <p className="text-xs text-muted-foreground">
          No detailed hardening checks available.
        </p>
      )}
    </div>
  );
}
