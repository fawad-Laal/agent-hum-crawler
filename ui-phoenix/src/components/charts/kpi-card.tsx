import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

interface KPICardProps {
  label: string;
  value: string | number;
  icon: LucideIcon;
  /** Subtitle/description under the value */
  subtitle?: string;
  /** Determines accent color: pass = green, fail = red, info = blue */
  tone?: "pass" | "fail" | "info" | "neutral";
}

const toneClasses = {
  pass: "text-status-pass",
  fail: "text-status-fail",
  info: "text-secondary",
  neutral: "text-foreground",
};

const iconBgClasses = {
  pass: "bg-status-pass/10",
  fail: "bg-status-fail/10",
  info: "bg-secondary/10",
  neutral: "bg-muted",
};

export function KPICard({ label, value, icon: Icon, subtitle, tone = "neutral" }: KPICardProps) {
  return (
    <Card className="flex items-start gap-4 p-5">
      <div className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-lg", iconBgClasses[tone])}>
        <Icon className={cn("h-5 w-5", toneClasses[tone])} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </p>
        <p className={cn("mt-1 text-2xl font-bold tabular-nums", toneClasses[tone])}>
          {value}
        </p>
        {subtitle && (
          <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p>
        )}
      </div>
    </Card>
  );
}

export function KPICardSkeleton() {
  return (
    <Card className="flex items-start gap-4 p-5">
      <Skeleton className="h-10 w-10 rounded-lg" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-7 w-20" />
        <Skeleton className="h-3 w-24" />
      </div>
    </Card>
  );
}
