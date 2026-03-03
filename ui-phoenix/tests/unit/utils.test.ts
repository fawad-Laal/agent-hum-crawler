import { describe, it, expect } from "vitest";
import { cn, fmtNumber, fmtPercent, fmtDate, fmtRelativeTime, fmtMatchReasons, freshnessTone } from "@/lib/utils";

describe("cn (class merge)", () => {
  it("merges tailwind classes", () => {
    const result = cn("px-2 py-1", "px-4");
    expect(result).toContain("px-4");
    expect(result).toContain("py-1");
    expect(result).not.toContain("px-2");
  });

  it("handles conditional classes", () => {
    expect(cn("base", false && "hidden")).toBe("base");
    expect(cn("base", true && "visible")).toBe("base visible");
  });
});

describe("fmtNumber", () => {
  it("formats null as -", () => {
    expect(fmtNumber(null)).toBe("-");
    expect(fmtNumber(undefined)).toBe("-");
  });

  it("formats small numbers with decimals", () => {
    expect(fmtNumber(0.123)).toBe("0.123");
  });

  it("formats large numbers with locale", () => {
    const result = fmtNumber(12345);
    expect(result).toContain("12");
  });
});

describe("fmtPercent", () => {
  it("formats 0-1 range as percentage", () => {
    expect(fmtPercent(0.85)).toBe("85.0%");
    expect(fmtPercent(1)).toBe("100.0%");
  });

  it("handles null", () => {
    expect(fmtPercent(null)).toBe("-");
  });
});

describe("fmtRelativeTime", () => {
  it("returns - for null", () => {
    expect(fmtRelativeTime(null)).toBe("-");
  });

  it("returns 'just now' for recent timestamps", () => {
    const now = new Date().toISOString();
    expect(fmtRelativeTime(now)).toBe("just now");
  });

  it("returns 'in the future' for future timestamps", () => {
    const future = new Date(Date.now() + 600_000).toISOString();
    expect(fmtRelativeTime(future)).toBe("in the future");
  });
});

describe("fmtDate", () => {
  it("returns - for null", () => {
    expect(fmtDate(null)).toBe("-");
    expect(fmtDate(undefined)).toBe("-");
  });

  it("formats a valid ISO date", () => {
    const result = fmtDate("2025-06-15T12:30:00Z");
    expect(result).toContain("Jun");
    expect(result).toContain("2025");
  });

  it("returns raw string for invalid date", () => {
    expect(fmtDate("not-a-date")).toBe("not-a-date");
  });
});

describe("fmtMatchReasons", () => {
  it("formats match reasons", () => {
    expect(fmtMatchReasons({ country_miss: 3, hazard_miss: 1, age_filtered: 5 }))
      .toBe("country:3 | hazard:1 | age:5");
  });

  it("handles empty", () => {
    expect(fmtMatchReasons({})).toBe("country:0 | hazard:0 | age:0");
  });
});

describe("freshnessTone", () => {
  it("maps fresh → ok", () => expect(freshnessTone("fresh")).toBe("ok"));
  it("maps stale → fail", () => expect(freshnessTone("stale")).toBe("fail"));
  it("maps unknown → muted", () => expect(freshnessTone("unknown")).toBe("muted"));
});
