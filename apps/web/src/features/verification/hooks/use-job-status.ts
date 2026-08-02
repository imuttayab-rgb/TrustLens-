'use client';

import { api } from '@/lib/api/client';
import { qk } from '@/lib/api/query-keys';
import { toApiError } from '@trustlens/api-client';
import { useQuery } from '@tanstack/react-query';

export type JobState = 'queued' | 'in_progress' | 'complete' | 'not_found' | 'failed';

export interface JobStatus {
  jobId: string;
  status: JobState;
  result?: unknown;
  enqueuedAt?: string;
  finishedAt?: string;
}

const TERMINAL: ReadonlySet<JobState> = new Set(['complete', 'failed', 'not_found']);

/**
 * Poll a background job until it settles.
 *
 * Identity verification runs OCR and a face match in the worker and takes
 * 15-30 seconds, so the UI cannot wait on the request. It polls instead.
 *
 * The interval widens as the job runs: a job that finishes quickly is noticed
 * quickly, while a slow one does not generate a request every second for half
 * a minute. Polling stops the moment the job reaches a terminal state, and
 * again after `timeoutMs` so a lost job cannot leave a tab polling forever.
 */
export function useJobStatus(
  jobId: string | null,
  { timeoutMs = 180_000 }: { timeoutMs?: number } = {},
) {
  return useQuery<JobStatus>({
    queryKey: qk.job.status(jobId ?? 'none'),
    enabled: Boolean(jobId),
    queryFn: async () => {
      const result = await api.GET('/api/v1/jobs/{job_id}', {
        params: { path: { job_id: jobId as string } },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as { data: JobStatus }).data;
    },
    refetchInterval: (query) => {
      const state = query.state.data?.status;
      if (state && TERMINAL.has(state)) return false;

      // Stop chasing a job that will never settle, so a forgotten tab does
      // not poll indefinitely.
      const firstSeen = query.state.dataUpdatedAt;
      if (firstSeen && Date.now() - firstSeen > timeoutMs) return false;

      // Back off: 1s for the first few checks, then 2s, then 4s.
      const polls = query.state.dataUpdateCount;
      if (polls < 5) return 1_000;
      if (polls < 15) return 2_000;
      return 4_000;
    },
    // A job that has not been picked up yet legitimately 404s for a moment.
    retry: (failureCount, error) =>
      (error as { status?: number })?.status === 404 && failureCount < 3,
    staleTime: 0,
  });
}
