import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

type BadgeVariant = "default" | "secondary" | "destructive" | "outline" | "success" | "warning";

const variantClasses: Record<BadgeVariant, string> = {
  default: "bg-primary text-primary-foreground",
  secondary: "bg-secondary/20 text-secondary",
  destructive: "bg-destructive/20 text-destructive",
  outline: "border border-border text-foreground",
  success: "bg-status-pass/20 text-status-pass",
  warning: "bg-status-warn/20 text-status-warn",
};

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2.5 py-0.5 text-xs font-medium transition-colors",
        variantClasses[variant],
        className
      )}
      {...props}
    />
  );
}
