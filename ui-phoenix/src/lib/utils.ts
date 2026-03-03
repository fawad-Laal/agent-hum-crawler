import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind classes with clsx support */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format a number for display (matches original fmtNumber) */
export function fmtNumber(v: unknown, digits = 3): string {
  if (v === null || v === undefined) return "-";
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  if (Math.abs(n) < 1) return n.toFixed(digits);
  return n.toLocaleString();
}

/** Format a percentage (0-1 range) for display */
export function fmtPercent(v: unknown, digits = 1): string {
  if (v === null || v === undefined) return "-";
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  return `${(n * 100).toFixed(digits)}%`;
}

/** Format ISO date to human-readable */
export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "-";
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

/** Format relative time (e.g. "2 hours ago") */
export function fmtRelativeTime(iso: string | null | undefined): string {
  if (!iso) return "-";
  try {
    const diff = Date.now() - new Date(iso).getTime();
    if (diff < 0) return "in the future";
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
  } catch {
    return iso;
  }
}

/** Format match reasons from source check */
export function fmtMatchReasons(reasons: {
  country_miss?: number;
  hazard_miss?: number;
  age_filtered?: number;
}): string {
  const country = Number(reasons?.country_miss ?? 0);
  const hazard = Number(reasons?.hazard_miss ?? 0);
  const age = Number(reasons?.age_filtered ?? 0);
  return `country:${country} | hazard:${hazard} | age:${age}`;
}

/** Freshness status → CSS tone */
export function freshnessTone(status: string): "ok" | "fail" | "muted" {
  if (status === "fresh") return "ok";
  if (status === "stale") return "fail";
  return "muted";
}
