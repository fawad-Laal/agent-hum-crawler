/**
 * Project Phoenix — useJobStream (Phase 8)
 * Opens an EventSource to GET /api/jobs/{jobId}/stream and returns
 * live job status updates. Registers the job in the global jobs store
 * so any page can show an active-jobs indicator via GlobalJobBadge.
 *
 * Usage:
 *   const { status, result, error } = useJobStream(jobId, "Running cycle");
 */

import { useEffect, useState } from "react";
import { useJobsStore } from "@/stores/jobs-store";
import type { JobStatus } from "@/stores/jobs-store";

export interface JobStreamState<T = unknown> {
  status: JobStatus | null;
  result: T | null;
  error: string | null;
  /** True while status is queued or running. */
  isActive: boolean;
}

/**
 * Subscribe to SSE updates for a single background job.
 *
 * @param jobId  Job token returned by a 202 POST endpoint. Pass `null` to
 *               disable (hook becomes a no-op).
 * @param label  Human-readable label shown in the global job status badge.
 */
export function useJobStream<T = unknown>(
  jobId: string | null,
  label = "Job in progress",
): JobStreamState<T> {
  const [state, setState] = useState<JobStreamState<T>>({
    status: null,
    result: null,
    error: null,
    isActive: false,
  });

  const addJob = useJobsStore((s) => s.addJob);
  const updateJob = useJobsStore((s) => s.updateJob);
  const removeJob = useJobsStore((s) => s.removeJob);

  useEffect(() => {
    if (!jobId) return;

    addJob(jobId, label);
    setState({ status: "queued", result: null, error: null, isActive: true });

    const es = new EventSource(`/api/jobs/${jobId}/stream`);

    es.onmessage = (event: MessageEvent<string>) => {
      try {
        const data = JSON.parse(event.data) as {
          job_id: string;
          status: JobStatus;
          result?: T;
          error?: string;
        };

        setState({
          status: data.status,
          result: data.result ?? null,
          error: data.error ?? null,
          isActive: data.status === "queued" || data.status === "running",
        });

        updateJob(jobId, data.status);

        if (data.status === "done" || data.status === "error") {
          es.close();
          // Keep the entry briefly so the badge can show "done" before fading
          setTimeout(() => removeJob(jobId), 3_000);
        }
      } catch {
        // Heartbeat comments (": ping") don't trigger onmessage — ignore parse errors
      }
    };

    es.onerror = () => {
      setState((prev) => ({
        ...prev,
        status: "error",
        error: "Stream connection lost",
        isActive: false,
      }));
      updateJob(jobId, "error");
      es.close();
      setTimeout(() => removeJob(jobId), 3_000);
    };

    return () => {
      es.close();
      removeJob(jobId);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, label]);

  return state;
}
