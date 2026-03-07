/**
 * Phase 10.1 — Zustand Store Tests
 * Covers stores/jobs-store.ts and stores/ui-store.ts
 */

import { describe, it, expect, beforeEach } from "vitest";
import { useJobsStore } from "@/stores/jobs-store";
import { useUIStore } from "@/stores/ui-store";

// ── Jobs Store ────────────────────────────────────────────────

describe("useJobsStore", () => {
  beforeEach(() => {
    // Reset to clean state before each test
    useJobsStore.setState({ jobs: {} });
  });

  it("starts with empty jobs map", () => {
    expect(useJobsStore.getState().jobs).toEqual({});
  });

  it("addJob creates a queued entry with a label and startedAt", () => {
    const before = Date.now();
    useJobsStore.getState().addJob("j1", "Run Cycle");
    const job = useJobsStore.getState().jobs["j1"];
    expect(job.label).toBe("Run Cycle");
    expect(job.status).toBe("queued");
    expect(job.startedAt).toBeGreaterThanOrEqual(before);
  });

  it("addJob preserves existing jobs", () => {
    useJobsStore.getState().addJob("j1", "Job 1");
    useJobsStore.getState().addJob("j2", "Job 2");
    expect(Object.keys(useJobsStore.getState().jobs)).toHaveLength(2);
  });

  it("updateJob changes the status of an existing job", () => {
    useJobsStore.getState().addJob("j1", "Run Cycle");
    useJobsStore.getState().updateJob("j1", "running");
    expect(useJobsStore.getState().jobs["j1"].status).toBe("running");
  });

  it("updateJob is a no-op when the job id does not exist", () => {
    useJobsStore.getState().updateJob("nonexistent", "done");
    expect(useJobsStore.getState().jobs).toEqual({});
  });

  it("removeJob deletes the entry by id", () => {
    useJobsStore.getState().addJob("j1", "Run Cycle");
    useJobsStore.getState().removeJob("j1");
    expect(useJobsStore.getState().jobs["j1"]).toBeUndefined();
  });

  it("removeJob is a no-op when id is not present", () => {
    useJobsStore.getState().addJob("j1", "Run Cycle");
    useJobsStore.getState().removeJob("nonexistent");
    expect(Object.keys(useJobsStore.getState().jobs)).toHaveLength(1);
  });

  it("getJob returns the job entry when it exists", () => {
    useJobsStore.getState().addJob("j1", "Run Cycle");
    const job = useJobsStore.getState().getJob("j1");
    expect(job?.label).toBe("Run Cycle");
  });

  it("getJob returns undefined when id not present", () => {
    expect(useJobsStore.getState().getJob("missing")).toBeUndefined();
  });

  it("activeCount counts only queued and running jobs", () => {
    useJobsStore.getState().addJob("j1", "Job 1");          // queued
    useJobsStore.getState().addJob("j2", "Job 2");          // queued
    useJobsStore.getState().updateJob("j2", "running");     // running
    useJobsStore.getState().addJob("j3", "Job 3");          // queued
    useJobsStore.getState().updateJob("j3", "done");        // done — not counted
    expect(useJobsStore.getState().activeCount()).toBe(2);
  });

  it("activeCount returns 0 when all jobs are done/error", () => {
    useJobsStore.getState().addJob("j1", "Job 1");
    useJobsStore.getState().updateJob("j1", "done");
    useJobsStore.getState().addJob("j2", "Job 2");
    useJobsStore.getState().updateJob("j2", "error");
    expect(useJobsStore.getState().activeCount()).toBe(0);
  });

  it("activeCount returns 0 on empty store", () => {
    expect(useJobsStore.getState().activeCount()).toBe(0);
  });

  it("full lifecycle: add → running → done → remove", () => {
    useJobsStore.getState().addJob("j1", "Pipeline");
    expect(useJobsStore.getState().activeCount()).toBe(1);

    useJobsStore.getState().updateJob("j1", "running");
    expect(useJobsStore.getState().activeCount()).toBe(1);

    useJobsStore.getState().updateJob("j1", "done");
    expect(useJobsStore.getState().activeCount()).toBe(0);

    useJobsStore.getState().removeJob("j1");
    expect(useJobsStore.getState().jobs).toEqual({});
  });
});

// ── UI Store ──────────────────────────────────────────────────

describe("useUIStore", () => {
  beforeEach(() => {
    // Reset to known initial state
    useUIStore.setState({ sidebarOpen: true });
  });

  it("starts with sidebarOpen: true", () => {
    expect(useUIStore.getState().sidebarOpen).toBe(true);
  });

  it("toggleSidebar closes the sidebar when it is open", () => {
    useUIStore.getState().toggleSidebar();
    expect(useUIStore.getState().sidebarOpen).toBe(false);
  });

  it("toggleSidebar opens the sidebar when it is closed", () => {
    useUIStore.setState({ sidebarOpen: false });
    useUIStore.getState().toggleSidebar();
    expect(useUIStore.getState().sidebarOpen).toBe(true);
  });

  it("setSidebarOpen directly sets the value to true", () => {
    useUIStore.setState({ sidebarOpen: false });
    useUIStore.getState().setSidebarOpen(true);
    expect(useUIStore.getState().sidebarOpen).toBe(true);
  });

  it("setSidebarOpen directly sets the value to false", () => {
    useUIStore.getState().setSidebarOpen(false);
    expect(useUIStore.getState().sidebarOpen).toBe(false);
  });

  it("double toggle returns to original state", () => {
    const initial = useUIStore.getState().sidebarOpen;
    useUIStore.getState().toggleSidebar();
    useUIStore.getState().toggleSidebar();
    expect(useUIStore.getState().sidebarOpen).toBe(initial);
  });
});
