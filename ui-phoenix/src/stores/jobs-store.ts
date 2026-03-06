/**
 * Project Phoenix — Active Jobs Store (Phase 8)
 * Tracks in-flight background jobs across navigation.
 * Used by GlobalJobBadge and mutation hooks to show live job status.
 */

import { create } from "zustand";

export type JobStatus = "queued" | "running" | "done" | "error";

interface JobEntry {
  label: string;
  status: JobStatus;
  /** Client-side timestamp (ms since epoch) when addJob was called — used for elapsed display (R18). */
  startedAt: number;
}

interface JobsState {
  jobs: Record<string, JobEntry>;
  addJob: (id: string, label: string) => void;
  updateJob: (id: string, status: JobStatus) => void;
  removeJob: (id: string) => void;
  getJob: (id: string) => JobEntry | undefined;
  /** Number of jobs currently queued or running. */
  activeCount: () => number;
}

export const useJobsStore = create<JobsState>((set, get) => ({
  jobs: {},

  addJob: (id, label) =>
    set((s) => ({
      jobs: { ...s.jobs, [id]: { label, status: "queued", startedAt: Date.now() } },
    })),

  updateJob: (id, status) =>
    set((s) => {
      if (!s.jobs[id]) return s;
      return { jobs: { ...s.jobs, [id]: { ...s.jobs[id], status } } };
    }),

  removeJob: (id) =>
    set((s) => {
      const next = { ...s.jobs };
      delete next[id];
      return { jobs: next };
    }),

  getJob: (id) => get().jobs[id],

  activeCount: () => {
    const { jobs } = get();
    return Object.values(jobs).filter(
      (j) => j.status === "queued" || j.status === "running",
    ).length;
  },
}));
