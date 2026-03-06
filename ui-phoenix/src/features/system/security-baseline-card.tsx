/**
 * SecurityBaselineCard — aggregates security posture from hardening gate,
 * E2E security_status, and hardening check details into a single status card.
 *
 * States (R17):
 *   critical — BOTH hardening gate AND E2E security failed
 *   fail     — hardening gate failed (E2E clean or absent)
 *   warn     — hardening gate passed but E2E security failed
 *   pass     — hardening gate passed, no E2E failure
 *   unknown  — no hardening data available
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

type SecurityLevel = "pass" | "warn" | "fail" | "critical" | "unknown";

function deriveLevel(
  hardening: HardeningStatus | undefined,
  e2eSummary: E2ESummary | null | undefined
): SecurityLevel {
  if (!hardening) return "unknown";
  const hardeningFail = hardening.status === "fail";
  const e2eFail = e2eSummary?.security_status === "fail";
  // Combined failure → critical (R17: never silently downgrade to warn)
  if (hardeningFail && e2eFail) return "critical";
  if (hardeningFail) return "fail";
  if (e2eFail) return "warn";
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
    /** Visible reason text shown below the label for every state (R17). */
    tooltip: string;
  }
> = {
  pass: {
    icon: <ShieldCheck className="h-10 w-10" />,
    label: "Baseline Secure",
    variant: "success",
    color: "text-status-pass",
    tooltip: "All hardening gates passed and E2E security is clean.",
  },
  warn: {
    icon: <ShieldAlert className="h-10 w-10" />,
    label: "Partial Compliance",
    variant: "warning",
    color: "text-warning",
    tooltip:
      "Hardening gate passed but the last E2E security check failed. Review E2E output.",
  },
  fail: {
    icon: <ShieldOff className="h-10 w-10" />,
    label: "Baseline Failing",
    variant: "destructive",
    color: "text-status-fail",
    tooltip:
      "Hardening gate failed. Fix the checks below before deploying.",
  },
  critical: {
    icon: <ShieldAlert className="h-10 w-10" />,
    label: "Critical Failure",
    variant: "destructive",
    color: "text-status-fail",
    tooltip:
      "Both the hardening gate and E2E security check failed. Immediate action required.",
  },
  unknown: {
    icon: <ShieldOff className="h-10 w-10" />,
    label: "Status Unknown",
    variant: "secondary",
    color: "text-muted-foreground",
    tooltip:
      "No hardening data available. Run a collection cycle to evaluate security posture.",
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
          {/* Reason tooltip — always rendered for every state (R17) */}
          <p className="text-xs text-muted-foreground mt-0.5">{cfg.tooltip}</p>
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
