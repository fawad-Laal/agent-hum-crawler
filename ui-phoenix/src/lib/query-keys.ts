/**
 * Project Phoenix — TanStack Query Key Constants
 * Single source of truth for all query keys used across
 * use-queries.ts and use-mutations.ts cache invalidation.
 */

export const QUERY_KEYS = {
  overview: ["overview"] as const,
  reports: ["reports"] as const,
  report: (name: string) => ["report", name] as const,
  systemInfo: ["system-info"] as const,
  countrySources: ["country-sources"] as const,
  workbenchProfiles: ["workbench-profiles"] as const,
  health: ["health"] as const,
  // Database
  dbCycles: (limit: number) => ["db", "cycles", limit] as const,
  dbEvents: (params: { limit?: number; country?: string; disaster_type?: string }) =>
    ["db", "events", params] as const,
  dbRawItems: (limit: number) => ["db", "raw-items", limit] as const,
  dbFeedHealth: (limit: number) => ["db", "feed-health", limit] as const,
} as const;
