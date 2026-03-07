/**
 * Phase 10.1 — Query Key Tests
 * Covers lib/query-keys.ts: all QUERY_KEYS constants and factory functions.
 */

import { describe, it, expect } from "vitest";
import { QUERY_KEYS } from "@/lib/query-keys";

describe("QUERY_KEYS — static keys", () => {
  it("overview key is ['overview']", () => {
    expect(QUERY_KEYS.overview).toEqual(["overview"]);
  });

  it("reports key is ['reports']", () => {
    expect(QUERY_KEYS.reports).toEqual(["reports"]);
  });

  it("systemInfo key is ['system-info']", () => {
    expect(QUERY_KEYS.systemInfo).toEqual(["system-info"]);
  });

  it("countrySources key is ['country-sources']", () => {
    expect(QUERY_KEYS.countrySources).toEqual(["country-sources"]);
  });

  it("workbenchProfiles key is ['workbench-profiles']", () => {
    expect(QUERY_KEYS.workbenchProfiles).toEqual(["workbench-profiles"]);
  });

  it("health key is ['health']", () => {
    expect(QUERY_KEYS.health).toEqual(["health"]);
  });
});

describe("QUERY_KEYS — factory functions", () => {
  it("report(name) returns ['report', name]", () => {
    expect(QUERY_KEYS.report("my-report.md")).toEqual(["report", "my-report.md"]);
  });

  it("report distinguishes different names", () => {
    expect(QUERY_KEYS.report("a.md")).not.toEqual(QUERY_KEYS.report("b.md"));
  });

  it("dbCycles(limit) returns ['db', 'cycles', limit]", () => {
    expect(QUERY_KEYS.dbCycles(50)).toEqual(["db", "cycles", 50]);
  });

  it("dbCycles uses its numeric argument", () => {
    expect(QUERY_KEYS.dbCycles(10)).toEqual(["db", "cycles", 10]);
    expect(QUERY_KEYS.dbCycles(100)).toEqual(["db", "cycles", 100]);
  });

  it("dbEvents(params) returns ['db', 'events', params]", () => {
    const params = { limit: 50, country: "Lebanon" };
    expect(QUERY_KEYS.dbEvents(params)).toEqual(["db", "events", params]);
  });

  it("dbEvents keys differ for different params objects", () => {
    const k1 = QUERY_KEYS.dbEvents({ country: "Lebanon" });
    const k2 = QUERY_KEYS.dbEvents({ country: "Pakistan" });
    expect(k1[2]).not.toEqual(k2[2]);
  });

  it("dbRawItems(limit) returns ['db', 'raw-items', limit]", () => {
    expect(QUERY_KEYS.dbRawItems(75)).toEqual(["db", "raw-items", 75]);
  });

  it("dbFeedHealth(limit) returns ['db', 'feed-health', limit]", () => {
    expect(QUERY_KEYS.dbFeedHealth(20)).toEqual(["db", "feed-health", 20]);
  });

  it("extractionDiagnostics(params) embeds params in key", () => {
    const p = { limit_cycles: 3, connector: "rss" };
    expect(QUERY_KEYS.extractionDiagnostics(p)).toEqual([
      "db",
      "extraction-diagnostics",
      p,
    ]);
  });

  it("extractionDiagnostics with empty params returns base key", () => {
    const key = QUERY_KEYS.extractionDiagnostics({});
    expect(key[0]).toBe("db");
    expect(key[1]).toBe("extraction-diagnostics");
  });
});
